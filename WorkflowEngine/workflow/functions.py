# !/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys, requests, json
from django.core.wsgi import get_wsgi_application
from requests.auth import HTTPBasicAuth

WorkflowEngine = os.path.dirname(os.path.dirname((os.path.abspath(__file__))))
sys.path.insert(0, WorkflowEngine)

import WorkflowEngine

os.environ['DJANGO_SETTINGS_MODULE'] = 'WorkflowEngine.settings'
application = get_wsgi_application()


import os, traceback
from django.template import Context, loader
from workflow import serializers, models
from errors import BadRequest
from error_list import error_list

from logger import logger
def create_workflow_wholeparam(data, belong_to):
    states = data['states']
    transitions = data['transitions']
    workflow = data['workflow']
    
    # validation
    wo_serializer = serializers.WorkflowSerializer(data=workflow)
    states_serializer = serializers.StateSerializer(data=states, many=True)
    if not wo_serializer.is_valid():
        raise BadRequest(error_list['parameter_error'], wo_serializer.errors)
    if not states_serializer.is_valid():
        raise BadRequest(error_list['parameter_error'], states_serializer.errors)

    states_name_list = [ elem['name'] for elem in states ]
    for elem in transitions:
        if elem['from_state'] not in states_name_list or elem['to_state'] not in states_name_list:
            raise BadRequest(error_list['parameter_error'], 
                'from_state or to_state of transition error')

    workflowobj = wo_serializer.save(belong_to=belong_to)
    states_serializer.save(workflow=workflowobj)
    states_query = workflowobj.states.all()
    try:
        for elem in transitions:
            models.Transition.objects.create(
                name=elem['name'],
                from_state=states_query.get(name=elem['from_state']),
                to_state=states_query.get(name=elem['to_state']),
                callback=elem.get('callback'),
                condition=elem.get('condition'),
                workflow=workflowobj)
    except Exception, e:
        raise BadRequest(error_list['parameter_error'])

    errors = None
    if not workflowobj.is_valid():
        errors = workflowobj.errors
    if errors and workflowobj.status==1:
        workflowobj.status = 0
        workflowobj.save()

    if not data.get('template'):
        workflowobj.cloned_from = workflowobj
        workflowobj.save()

    states_model = workflowobj.states.all()
    index = 0
    for state in states_model:
        participants = states[index].get('participants', [])
        index += 1
        if participants:
            state.participants.clear()
            for p in participants:
                state.participants.add(models.Participant.objects.create(executor=p))
            state.save()
    return workflowobj

def get_dotfile(workflow, current_state):
    """
    Given a workflow will return the appropriate contents of a .dot file for 
    processing by graphviz
    """
    c = Context({'workflow': workflow, 'current_state': current_state})
    t = loader.get_template('graphviz/workflow.dot')
    return t.render(c)

def get_history_dotfile(histories):
    c = Context({'histories': histories})
    t = loader.get_template('graphviz/histories.dot')
    return t.render(c)
    
def create_workflow_by_file(filename, user):
    try:
        cmd = 'from %s import data' % filename
        exec(cmd)
        data['workflow']['template'] = True
        workflowobj = create_workflow_wholeparam(data, user)
        os.remove('./workflow/'+filename+'.py')
        return workflowobj
    except Exception, e:
        os.remove('./workflow/'+filename+'.py')
        raise BadRequest(error_list['parameter_error'], str(e))

def get_participant_current_task(executor, belong_to):
    print type(executor)
    states = models.State.objects.filter(
        workflow__belong_to=belong_to,
        workflow__cloned_from__isnull=False,
        workflow__workflowactivity__status=models.WorkflowActivity.EXECUTE,
        participants__executor=executor).distinct()
    print states.count()
    exclude = models.State.objects.none()
    # for state in states:
    #     if state.get_status() != 'processing':
    #         exclude |= models.State.objects.filter(pk=state.id)
    # states = states.exclude(exclude)
    # print states.count()
    return serializers.TaskSerializer(states, many=True).data


def get_user_delegate_task(executor, belong_to):
    return models.State.objects.filter(
        workflow__belong_to=belong_to,
        workflow__workflowactivity__status=models.WorkflowActivity.EXECUTE,
        participants__executor=executor,
        participants__delegate_to__isnull=False
        )
def classify_user_task(queryset, executor):
    data = {
        'future': [],
        'completed': [],
        'executing': []
    }
    for stateobj in queryset:
        workflowactivity = stateobj.workflow.workflowactivity
        if workflowactivity.status==models.WorkflowActivity.EXECUTE:
            current_history = workflowactivity.current_state()
            current_state = current_history.state
            if stateobj.sequence < current_state.sequence:
                data['completed'].append(stateobj)
            elif stateobj.sequence > current_state.sequence:
                data['future'].append(stateobj)
            else:
                if current_history.records.filter(
                    participant__executor=executor, action=models.Record.PASS):
                    data['completed'].append(stateobj)
                else:
                    data['executing'].append(stateobj)
        else:
            data['completed'].append(stateobj)
    return data
def get_user_delegated_executing_task(executor, belong_to):
    executing, completed, future = [], [], []
    queryset = models.State.objects.filter(
        workflow__belong_to=belong_to,
        workflow__workflowactivity__status=models.WorkflowActivity.EXECUTE,
        participants__delegate_to__executor=executor).distinct()
    for stateobj in queryset:
        workflowactivity = stateobj.workflow.workflowactivity
        current_history = workflowactivity.current_state()
        current_state = current_history.state
        if current_state==stateobj and (not current_history.records.filter(
            participant__executor=executor, action=models.Record.PASS)):
            executing.append(stateobj)
        elif current_state.sequence > stateobj.sequence:
            completed.append(stateobj)
        elif current_state.sequence < stateobj.sequence:
            future.append(stateobj)

    queryset = models.State.objects.filter(
        workflow__belong_to=belong_to,
        workflow__workflowactivity__status=models.WorkflowActivity.COMPLETE,
        participants__delegate_to__executor=executor).distinct()
    completed.extend(queryset)
    return executing, completed, future
def get_pariticipant_task(executor, belong_to):
    queryset = models.State.objects.filter(
        workflow__belong_to=belong_to,
        workflow__workflowactivity__status__gte=models.WorkflowActivity.EXECUTE,
        workflow__workflowactivity__status__lte=models.WorkflowActivity.COMPLETE,
        participants__executor=executor,
        participants__delegate_to__isnull=True)
    task_classify = classify_user_task(queryset, executor)
    executing, completed, future = get_user_delegated_executing_task(executor, belong_to)
    task_classify['executing'].extend(executing)
    task_classify['completed'].extend(completed)
    task_classify['future'].extend(future)
    task_classify['delegate'] = get_user_delegate_task(executor, belong_to)
    return task_classify
def get_participant_task_data(executor, belong_to):
    task = get_pariticipant_task(executor, belong_to)
    task['executing'] = serializers.TaskSerializer(task['executing'], many=True).data
    task['future'] = serializers.TaskSerializer(task['future'], many=True).data
    task['completed'] = serializers.TaskSerializer(task['completed'], many=True).data
    task['delegate'] = serializers.TaskSerializer(task['delegate'], many=True).data
    return task

def change_workflowactivity_status(wa_instance, oldstatus, newstatus):
    if int(newstatus)==int(models.WorkflowActivity.COMMIT):
        success, result = wa_instance.start()
        return success, result
    wa_instance.status = int(newstatus)
    wa_instance.save()
    return True, wf_instance

if __name__ == '__main__':
    from django.contrib.auth.models import User
    user = User.objects.get(username='admin')
    create_workflow_by_file('test', user)