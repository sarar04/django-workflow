# !/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import unicode_literals
import json, datetime
from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import ugettext_lazy as _, ugettext as __
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
import django.dispatch

from error_list import error_list
from logger import logger

#########
# Signals
#########

# Fired when a role is assigned to a user for a particular run of a workflow
# (defined in the WorkflowActivity). The sender is an instance of the
# WorkflowHistory model logging this event.
role_assigned = django.dispatch.Signal()
# Fired when a role is removed from a user for a particular run of a workflow
# (defined in the WorkflowActivity). The sender is an instance of the
# WorkflowHistory model logging this event.
role_removed = django.dispatch.Signal()
# Fired when a new WorkflowActivity starts navigating a workflow. The sender is
# an instance of the WorkflowActivity model
workflow_started = django.dispatch.Signal()
# Fired just before a WorkflowActivity creates a new item in the Workflow History
# (the sender is an instance of the WorkflowHistory model)
workflow_pre_change = django.dispatch.Signal()
# Fired after a WorkflowActivity creates a new item in the Workflow History (the
# sender is an instance of the WorkflowHistory model)
workflow_post_change = django.dispatch.Signal() 
# Fired when a WorkflowActivity causes a transition to a new state (the sender is
# an instance of the WorkflowHistory model)
workflow_transitioned = django.dispatch.Signal()
# Fired when some event happens during the life of a WorkflowActivity (the 
# sender is an instance of the WorkflowHistory model)
workflow_event_completed = django.dispatch.Signal()
# Fired when a comment is created during the lift of a WorkflowActivity (the
# sender is an instance of the WorkflowHistory model)
workflow_commented = django.dispatch.Signal()
# Fired when an active WorkflowActivity reaches a workflow's end state. The
# sender is an instance of the WorkflowActivity model
workflow_ended = django.dispatch.Signal()

########
# Models
########
class Workflow(models.Model):
    DEFINITION = 0
    ACTIVE = 1
    RETIRED = 2

    STATUS_CHOICE_LIST  = (
                (DEFINITION, _('In definition')),
                (ACTIVE, _('Active')),
                (RETIRED, _('Retired')),
            )

    name = models.CharField(
            _('Workflow Name'),
            max_length=128
            )
    description = models.TextField(
            _('Description'),
            blank=True
            )
    status = models.IntegerField(
            _('Status'),
            choices=STATUS_CHOICE_LIST,
            default = DEFINITION
            )

    created_on = models.DateTimeField(auto_now_add=True)
    creator = JSONField(blank=True, null=True)
    cloned_from = models.ForeignKey(
            'self', 
            null=True
            )
    belong_to = models.ForeignKey(User, blank=True, null=True)
    token = models.TextField(null=True,blank=True)

    # To hold error messages created in the validate method
    errors = {
                'workflow':[], 
                'states': {},
                'transitions':{},
             }

    def is_valid(self):
        self.errors = {
                'workflow':[], 
                'states': {},
                'transitions':{},
             }
        valid = True

        # The graph must have only one start node
        if self.states.filter(state_type=State.START_STATE).count() != 1:
            self.errors['workflow'].append(__('There must be only one start'\
                ' state'))
            valid = False

        # The graph must have at least one end state
        if self.states.filter(state_type=State.END_STATE).count() < 1:
            self.errors['workflow'].append(__('There must be at least one end'\
                ' state'))
            valid = False

        # Check for orphan nodes / cul-de-sac nodes
        all_states = self.states.all()
        for state in all_states:
            # 非起点且无进入transition
            if state.transitions_into.all().count()==0 and state.state_type!=State.START_STATE:
                if not state.id in self.errors['states']:
                    self.errors['states'][state.id] = list()
                self.errors['states'][state.id].append(__('This state is'\
                        ' orphaned. There is no way to get to it given the'\
                        ' current workflow topology.'))
                valid = False
            # 非终点且无输出transition
            if state.transitions_from.all().count()==0 and state.state_type!=State.END_STATE:
                print state
                if not state.id in self.errors['states']:
                    self.errors['states'][state.id] = list()
                self.errors['states'][state.id].append(__('This state is a'\
                        ' dead end. It is not marked as an end state and there'\
                        ' is no way to exit from it.'))
                valid = False
        return valid

    def has_errors(self, thing):
        if isinstance(thing, State):
            if thing.id in self.errors['states']:
                return self.errors['states'][thing.id]
            else:
                return []
        elif isinstance(thing, Transition):
            if thing.id in self.errors['transitions']:
                return self.errors['transitions'][thing.id]
            else:
                return []
        else:
            return []

    def clone(self, creator):
        source = Workflow.objects.get(pk=self.id)

        # Clone this workflow
        clone_workflow = source
        clone_workflow.pk = None
        clone_workflow.cloned_from = self
        clone_workflow.save()

        # Clone the states
        state_dict = dict() # key = old pk of state, val = new clone state
        for s in self.states.all():
            ssource = State.objects.get(pk=s.id)
            clone_state = ssource
            clone_state.pk = None
            clone_state.workflow = clone_workflow
            clone_state.save()
            for p in s.participants.all():
                participant = Participant.objects.create(executor=p.executor)
                clone_state.participants.add(participant)
            clone_state.save()
            state_dict[s.id] = clone_state
        
        # Clone the transitions
        for tr in self.transitions.all():
            clone_trans = tr
            clone_trans.pk = None
            clone_trans.workflow = clone_workflow
            clone_trans.from_state = state_dict[tr.from_state.id]
            clone_trans.to_state = state_dict[tr.to_state.id]
            clone_trans.save()
        
        return clone_workflow

    def change_status(self, sstatus):
        if not self.is_valid():
            return False, self.errors
        if sstatus not in STATUS_CHOICE_LIST:
            return False, 'invalid status'
        self.status = sstatus
        self.save()
        return True, None

    def __unicode__(self):
        if not self.cloned_from:
            return self.name + '--template'
        return self.name + '--instance'

    class Meta:
        ordering = ['created_on']
        verbose_name = _('Workflow')
        verbose_name_plural = _('Workflows')
        permissions = (
                ('can_manage_workflows', __('Can manage workflows')),
            )

class Participant(models.Model):
    executor = JSONField(blank=True, null=True)
    delegate_to = models.ForeignKey('self', null=True, blank=True)
    delegate_on = models.TextField(null=True)
    copy = models.BooleanField(default=False)

    def copy(self):
        copy_participant = self
        copy_participant.copy = True
        copy_participant.pk = None
        copy_participant.save()
        return copy_participant

    def __unicode__(self):
        return 'participant-%d' % self.id

def resolve_queryset(queryset, state, exclude):
    if not queryset:
        return exclude
    new_state = queryset.filter(state=state)[0].transition.to_state
    newqueryset = queryset.exclude(created_on__gte=queryset.filter(state=new_state)[0].created_on)
    newqueryset = get_difference_set(queryset, newqueryset)
    exclude |= queryset.filter(state=state)
    return resolve_queryset(newqueryset, new_state, exclude)

def get_difference_set(seta, setb):
    differ = seta
    for elem in setb:
        differ = differ.exclude(pk=elem.id)
    return differ

class State(models.Model):
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    
    workflow = models.ForeignKey(Workflow, related_name='states')
    roles = JSONField(blank=True, null=True, default=[])  # must be list

    allow_delegation = models.BooleanField(default=True)
    allow_abolish = models.BooleanField(default=False)
    allow_state_edit = models.BooleanField(default=False)
    deadline_warning = models.BooleanField(default=True)
    auto_end = models.BooleanField(default=False)
    relation = models.FloatField(default=1, help_text='0-or, 1-and')

    END_STATE = 0
    START_STATE = 1
    GENERAL_STATE = 2
    SELECT_STATE = 3
    PARALLEL_STATE = 4
    JOINT_STATE = 5
    STATE_TYPE = (
        (END_STATE, _('End')),
        (START_STATE, _('Start')), 
        (GENERAL_STATE, _('General')),
        (SELECT_STATE, _('Select')),
        (PARALLEL_STATE, _('Parallel')),
        (JOINT_STATE, _('Joint'))
    )
    state_type = models.IntegerField(choices=STATE_TYPE, default=2)
    callback = JSONField(blank=True, null=True) # when state_type=3 needed
    
    # 流程实例中的节点属性
    participants = models.ManyToManyField(Participant, blank=True)
    deadline = models.DateField(null=True, blank=True)
    remark = JSONField(blank=True, null=True)

    def get_deadline(self):
        pass

    def get_actions(self):
        action_list = [elem.name for elem in self.transitions_from.all()]
        return list(set(action_list))

    def get_status(self):
        # solution 1
        try:
            if self.workflow.workflowactivity.status==WorkflowActivity.COMPLETE and \
                self.state_type == self.END_STATE:
                return 'finish'
            if self in self.workflow.workflowactivity.current_state():
                return 'processing'
            histories = self.workflow.workflowactivity.history.all().order_by('created_on')
            queryset = WorkflowHistory.objects.none()
            for h in histories:
                if queryset.filter(state=h.state):
                    newqueryset = queryset.exclude(created_on__gte=queryset.filter(state=h.state)[0].created_on)
                    newqueryset = get_difference_set(queryset, newqueryset)
                    exclude = queryset.filter(pk=-1)
                    exclude |= resolve_queryset(newqueryset, h.state, exclude)
                    queryset = get_difference_set(queryset, exclude)
                    queryset = queryset.exclude(created_on__gte=queryset.filter(state=h.state)[0].created_on)
                queryset |= histories.filter(pk=h.id)
            if queryset.filter(state=self):
                return queryset.get(state=self).status
            else:
                return 'undo'
        except Exception, e:
            print e
            return 'undo'

        # solution 2 has some problem
        try:
            if self.workflow.workflowactivity.status==WorkflowActivity.COMPLETE and \
                self.state_type == self.END_STATE:
                return 'finish'
            status = self.workflow.workflowactivity.history.filter(state=self).order_by('-created_on')[0].status
            histories = self.workflow.workflowactivity.history.order_by('-created_on')
            queryset = WorkflowHistory.objects.none()
            reject = False
            for index, h in enumerate(histories):
                if index == 0:
                    queryset |= histories.filter(pk=h.id)
                    continue 
                if h.state==histories[0].state:
                    # queryset |= histories.filter(pk=h.id)
                    reject = True
                    break
                queryset |= histories.filter(pk=h.id)
            if reject==True and queryset.filter(state=self):
                if self == histories[0].state:
                    return queryset.filter(state=self)[0].status
                else:
                    return "undo"
            else:
                return status
        except Exception, e:
            print e
            return 'undo'

    def auto_route(self):
        transitions = self.transitions_from.all()
        routes = []
        for t in transitions:
            if t.condition:
                field = t.condition.get('field')
                operator = t.condition.get('operator')
                value = t.condition.get('value')
                field_value = self.workflow.workflowactivity.subject.get(field, 0)
                if operator == "<=" and field_value<=value:
                    routes.append(t)
                    continue
                elif operator == "<" and field_value<value:
                    routes.append(t)
                    continue
                elif operator == ">=" and field_value>=value:
                    routes.append(t)
                    continue
                elif operator == ">" and field_value>value:
                    routes.append(t)
                    continue
                elif operator == "=" and field_value==value:
                    routes.append(t)
                    continue
        if routes:
            return routes
        return  transitions

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['id']
        verbose_name = _('State')
        verbose_name_plural = _('States')

class Transition(models.Model):
    """
    Represents how a workflow can move between different states. An edge 
    between state "nodes" in a directed graph.
    """
    name = models.CharField(max_length=255)
    condition = JSONField(blank=True, null=True)
    percent = models.FloatField(default=1,
            help_text='this field used when participants of from_state is many, range from 0 to 1, default=1'
        )
    workflow = models.ForeignKey(
            Workflow,
            related_name = 'transitions'
            )
    from_state = models.ForeignKey(
            State,
            related_name = 'transitions_from'
            )
    to_state = models.ForeignKey(
            State,
            related_name = 'transitions_into'
            )

    callback = JSONField(blank=True, null=True)

    def __unicode__(self):
        name = '{0}: {1}->{2}'.format(self.name, 
            self.from_state.name, self.to_state.name)
        return name

    class Meta:
        ordering = ['id']
        verbose_name = _('Transition')
        verbose_name_plural = _('Transitions')

class Record(models.Model):
    participant = models.ForeignKey(Participant, related_name='record')
    # processing/delegate and others(state.action)
    action = models.CharField(max_length=255)
    note = models.TextField()
    attachment = JSONField(blank=True, null=True)
    log_on = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return 'record-%s' % self.participant
    class Meta:
        ordering = ['-log_on']

class WorkflowActivity(models.Model):
    """
    Other models in a project reference this model so they become associated 
    with a particular workflow.

    The WorkflowActivity object also contains *all* the methods required to
    start, progress and stop a workflow.
    """
    EDIT = 0
    COMMIT = 1
    EXECUTE = 2
    COMPLETE = 3
    ABOLISHED = 4
    ERROR = 5

    WORKFLOWACTIVIT_STATUS = (
        (EDIT, _('Editing')),  # 仅编制人可见（对应实例化：保存）
        # 对应：提交, 
        # 对于自动启动流程（start_now=True），提交后，流程自动启动,处于执行中,流转到第一节点处
        # 对于非自启动，提交后，处于已提交状态，需手动启动
        (COMMIT, _('Commited')), 
        (EXECUTE, _('Executing')),
        (COMPLETE, _('Completed')),
        (ABOLISHED, _('Abolished')),
        (ERROR, _('Error')),
    )

    status = models.IntegerField(choices=WORKFLOWACTIVIT_STATUS, default=EDIT)

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    subject = JSONField(blank=True, null=True)

    workflow = models.OneToOneField(Workflow, related_name='workflowactivity')
    creator = JSONField(blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    plan_start_time = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)

    completed_on = models.DateTimeField(
            null=True,
            blank=True
            )
    real_start_time = models.DateTimeField(null=True, blank=True) # 流程启动时，自动添加

    def current_state(self):
        return self.workflow.states.filter(workflowhistory__status='processing')

    def get_state_participant_by_executor(self, state_obj, executor):
        # whether real executor
        participants = state_obj.participants.filter(executor=executor, 
            delegate_to__isnull=True)
        if participants:
            return participants[0]

        # whether delegated executor
        participants = state_obj.participants.filter(delegate_to__isnull=False, 
            delegate_to__executor=executor)
        if participants:
            return participants[0]
        return None
    
    def check_participant_of_next_state(self, state_obj, transitions):
        for transition in transitions:
            next_state = transition.to_state
            if next_state.state_type!=State.END_STATE and (not next_state.participants.all()):
                return False
        return True

    def update_state_status(self):
        # commit/start/progress need to call
        histories = self.history.all()
        for index,history in enumerate(histories, 1):
            state = history.state
            if state.state_type in [State.START_STATE, State.PARALLEL_STATE]:
                histories = histories[0:index]
        if histories.filter(state=histories[0].state).count() >= 1:
            pass

    def commit(self, creator):
        # check creator
        if creator != self.creator:
            error = error_list['only_creator_allowed']
            logger.info(error)
            return False, error

        # check status
        if self.status != self.EDIT:
            error = error_list['only_edit_allowed']
            logger.info(error)
            return False, error

        # change status
        self.status = self.COMMIT
        self.save()
        return True, None

    def start(self, creator):
        # Validation...
        # 1. check status
        if self.status != self.COMMIT:
            error = error_list['only_commit_allowed']
            return False, error

        # 2. There is exactly one start state
        start_state = State.objects.filter(
                workflow=self.workflow, 
                state_type=State.START_STATE
                )
        if start_state.count() != 1:
            error = error_list['multi_start_state']
            return False, error
        
        # 3. Only creator can start
        if self.creator != creator:
            error = error_list['only_creator_allowed']
            return False, error

        # 4. Check executor of start state
        start_state = start_state[0]
        if not start_state.participants.all():
            error = error_list['next_state_participant_needed']
            return False, error
        
        first_step = WorkflowHistory(
                workflowactivity=self,
                state=start_state,
                log_type=WorkflowHistory.TRANSITION
            )
        first_step.save()

        self.status = self.EXECUTE
        self.real_start_time = datetime.datetime.today()
        self.save()

        return True, first_step        
  
    def progress(self, state, transitions):
        # progress用于流程流转到下一节点，后台默认执行
        for transition in transitions:
            to_state = transition.to_state
            if to_state.state_type== State.END_STATE:
                self.completed_on = datetime.datetime.today()
                self.status = self.COMPLETE
                self.save()
            elif to_state.state_type==State.JOINT_STATE:
                intotrans = to_state.transitions_into.all()
                for t in intotrans:
                    if t.from_state.get_status() in ['undo', 'processing']:
                        return True, None
                wh = WorkflowHistory(
                        workflowactivity=self,
                        state=to_state,
                        log_type=WorkflowHistory.TRANSITION,
                        transition=transition,
                        deadline=to_state.get_deadline()
                        )
                wh.save()
            else:
                wh = WorkflowHistory(
                        workflowactivity=self,
                        state=to_state,
                        log_type=WorkflowHistory.TRANSITION,
                        transition=transition,
                        deadline=to_state.get_deadline()
                        )
                wh.save()
        return True, None

    def delete(self):
        # 删除records
        histories = self.history.all()
        for h in histories:
            records = h.records.all()
            for r in records:
                r.participant.delete()

        # 删除节点参与者
        states = self.workflow.states.all()
        for s in states:
            s.participants.all().delete()

        # delete workflow、states、transitions、workflowactivity
        self.workflow.delete()
        return None

  # ---------------------------------------------------------------------------------
    def log_event(self, state, executor, action, note='', attachment=None):
        if state.get_status() != 'processing':
            return False, error_list['only_progress_allowed']

        if action not in state.get_actions():
            return False, error_list['invalid_action']

        # 是否执行人
        participant_obj = self.get_state_participant_by_executor(
            state_obj=state, executor=executor)
        if not participant_obj:
            return False,error_list['invalid_executor']

        # 重复提交
        workflowhistory = state.workflowhistory_set.get(status='processing')
        records = workflowhistory.records.exclude(action='processing')
        for elem in records:
            if elem.participant.delegate_to and elem.participant.delegate_to.executor==executor:
                return False, error_list['repeated_logevent']
            if (not elem.participant.delegate_to) and (elem.participant.executor==executor):
                return False, error_list['repeated_logevent']

        # 流程流转判断: 做出相同动作的人是否达到relation设置的比例
        progress, transition = False, None
        transitions = state.transitions_from.filter(name=action)
        action_records = workflowhistory.records.filter(action=action)
        if (action_records.count()+1)*1.0/state.participants.count() >= state.relation:
            progress = True
            if state.state_type!=State.END_STATE:
                if state.state_type == State.PARALLEL_STATE:
                    transitions = transitions
                else:
                    if transitions.count() > 1:
                        transitions = state.auto_route()

        # 如果需要流转那么是否指定后续节点的执行人
        if transitions:
            res = self.check_participant_of_next_state(state, transitions)
            if not res:
                error = error_list['next_state_participant_needed']
                return res, error
        
        # 创建流程处理记录
        # update or create record
        record = workflowhistory.records.filter()
        record = Record.objects.create(
            participant=participant_obj.copy(),
            action=action,
            note=note,
            attachment=attachment
        )

        # update workflowhistory
        workflowhistory.records.add(record)
        workflowhistory.save()

        if progress:
            workflowhistory.status = action
            workflowhistory.save()
            if transitions:
                return self.progress(state, transitions)
            else:
                return True, workflowhistory
        else:
            return True, workflowhistory

    def delegation(self, user, delegator, reason='', attachment=None, 
        repeat=False):
        current_state = self.current_state()
        
        # 1.允许委托
        if not current_state.state.allow_delegation:
            error = error_list['delegate_denied']
            logger.info(error)
            return False, error

        # 2.无效的委托者
        participants = current_state.state.participants.all()
        participant = None
        for p in participants:
            if user==p.executor:
                participant = p
                break
        if not participant:
            error = error_list['invalid_executor']
            logger.info(error)
            return False, error
        
        # 3.只能委托一次且不可取消
        if participant.delegate_to:
            error = error_list['delegate_only_once']
            logger.info(error)
            return False, error

        if not repeat:
            # 4.不能委托给执行者以及执行者的已委托者
            error = False
            for elem in participants:
                if elem.delegate_to:
                    if delegator==elem.delegate_to.executor:
                        error = True
                        break
                else:
                    if delegator == elem.executor:
                        error = True
                        break
            if error:
                error = error_list['invalid_delegator']
                logger.info(error)
                return False, error

            new_participant = Participant.objects.create(executor=delegator)

            participant.delegate_to = new_participant
            participant.delegate_on = datetime.datetime.today()
            participant.save()
        else:
            new_participant = Participant.objects.create(executor=delegator)
            state = current_state.state
            state.participants = state.participants.exclude(executor=user)
            state.participants.add(new_participant)
            state.save()
            participant.delegate_to = new_participant
            participant.delegate_on = datetime.datetime.today()
            participant.save()

        record = Record.objects.create(
            participant=participant.copy(),
            action='delegate',
            note=reason,
            attachment=attachment
        )
        # update workflowhistory
        wh = current_state
        wh.records.add(record)
        wh.save()
        return True, self
    
    def abolish(self, creator):
        self.status = self.ABOLISHED
        self.save()
        return True, self

    # 当前节点的执行人可以更改后续节点
    def edit_state(self, user, new_state, old_state):
        current_state = self.current_state()

        if not current_state.state.allow_state_edit:
            error = error_list['edit_state_denied']
            logger.info(error)
            return False, error
        
        participant = self.get_state_participant_by_userjson(
            state_obj=current_state.state, user=user)
        if not participant:
            error = error_list['invalid_executor']
            logger.info(error)
            return False, error_list['invalid_executor']

        if (old_state not in self.workflow.states.all()) or (old_state.sequence<=current_state.state.sequence):
            error = error_list['only_follow_up_allowed']
            logger.info(error)
            return False, error_list['only_follow_up_allowed']

        logger.debug('update state')
        old_state.description = new_state.get('description', old_state.description)

        old_state.is_many = new_state.get('is_many', old_state.is_many)
        if old_state.is_many:
            old_state.is_and = new_state.get('is_and', old_state.is_and)
        
        old_state.allow_delegation = new_state.get('allow_delegation', old_state.allow_delegation)
        old_state.allow_abolish = new_state.get('allow_abolish', old_state.allow_abolish)

        old_state.allow_reject = new_state.get('allow_reject', old_state.allow_reject)
        if old_state.allow_reject:
            reject_to = new_state.get('reject_to', 1)
            if reject_to >= old_state.sequence or reject_to < 1:
                reject_to = 1
            old_state.reject_to = reject_to

        old_state.allow_state_edit = new_state.get('allow_state_edit', old_state.allow_state_edit)
        old_state.deadline_warning = new_state.get('deadline_warning', old_state.deadline_warning)
        old_state.save()

        new_participants = new_state.get('participants', None)
        if new_participants:
            old_participants = old_state.participants.all()
            old_participants.delete()

            for p in new_participants:
                participant = Participant.objects.create(executor=p['user'])
                old_state.participants.add(participant)

        old_state.save()
        return self

# -----------------------------------------------------------------
    def add_comment(self, user, note):
        pass

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['-created_on']
        verbose_name = _('Workflow Activity')
        verbose_name_plural = _('Workflow Activites')
        permissions = (
                ('can_start_workflow',__('Can start a workflow')),
                ('can_assign_roles',__('Can assign roles'))
            )

class WorkflowHistory(models.Model):
    """
    Records what has happened and when in a particular run of a workflow. The
    latest record for the referenced WorkflowActivity will indicate the current 
    state.
    """

    # The sort of things we can log in the workflow history
    TRANSITION = 1
    EVENT = 2
    ROLE = 3
    COMMENT = 4

    # Used to indicate what sort of thing we're logging in the workflow history
    TYPE_CHOICE_LIST = (
            (TRANSITION, _('Transition')),
            (EVENT, _('Event')),
            (ROLE, _('Role')),
            (COMMENT, _('Comment')),
            )

    workflowactivity= models.ForeignKey(
            WorkflowActivity,
            related_name='history')
    log_type = models.IntegerField(
            help_text=_('The sort of thing being logged'),
            choices=TYPE_CHOICE_LIST
            )
    state = models.ForeignKey(
            State,
            help_text=_('The state at this point in the workflow history'),
            null=True
            )
    transition = models.ForeignKey(
            Transition, 
            null=True,
            related_name='history',
            help_text=_('The transition relating to this happening in the'\
                ' workflow history')
            )
    created_on = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(
            _('Deadline'),
            null=True,
            blank=True,
            help_text=_('The deadline for staying in this state')
            )

    # 这两个字段需随流程的流转更新
    # processing and others(state.action)
    status = models.CharField(default='processing', max_length=255)
    records = models.ManyToManyField(Record, blank=True)

    def save(self):
        workflow_pre_change.send(sender=self)
        super(WorkflowHistory, self).save()
        workflow_post_change.send(sender=self)
        if self.log_type==self.TRANSITION:
            workflow_transitioned.send(sender=self)
        if self.log_type==self.COMMENT:
            workflow_commented.send(sender=self)
        if self.state:
            if self.state.state_type==State.START_STATE:
                workflow_started.send(sender=self.workflowactivity)
            elif self.state.state_type==State.END_STATE:
                workflow_ended.send(sender=self.workflowactivity)

    def __unicode__(self):
        return self.workflowactivity.name+'-'+self.state.name
    class Meta:
        ordering = ['created_on']
        verbose_name = _('Workflow History')
        verbose_name_plural = _('Workflow Histories')
