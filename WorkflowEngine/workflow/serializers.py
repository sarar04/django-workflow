# !/usr/bin/env python
# -*- coding: utf-8 -*-

import json, time
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers
from rest_framework.serializers import ValidationError

from workflow import models
from workflow import myserializers

class WorkflowPostSerializer(myserializers.ModelSerializer):
    class Meta:
        model = models.Workflow
        fields = ('id', 'name', 'description', 'status', 'creator', 'token')

class StatePostSerializer(myserializers.ModelSerializer):
    class Meta:
        model = models.State
        fields = ('id', 'name', 'description', 'roles', 'allow_delegation', 
            'allow_abolish', 'allow_state_edit', 'deadline_warning', 'remark', 
            'relation', 'state_type', 'deadline', 'callback')

class TransitionPostSerializer(myserializers.ModelSerializer):
    class Meta:
        model = models.Transition
        fields = ('id', 'name', 'from_state', 'to_state', 'callback', 'condition')


class ParticipantSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Participant
        fields = ('id', 'executor')

class ParticipantSerializer(serializers.ModelSerializer):
    delegate_to = ParticipantSimpleSerializer()
    class Meta:
        model = models.Participant
        fields = ('id', 'executor', 'delegate_to', 'delegate_on')


class StateSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.State
        fields = ('id', 'name')

class CurrentStateSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True)
    class Meta:
        model = models.State
        fields = ('id', 'name', 'participants')


class StateDetailSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True)
    class Meta:
        model = models.State
        fields = ('id', 'name', 'description', 'state_type',
            'workflow', 'allow_delegation', 'allow_abolish', 
            'allow_state_edit', 'deadline_warning',
            'participants', 'deadline', 'auto_end', 'remark')
    
    def to_representation(self, instance):
        ret = super(StateDetailSerializer, self).to_representation(instance)
        ret['actions'] = instance.get_actions()
        ret['status'] = instance.get_status()
        return ret

class WorkflowActivityStatePatchSerializer(serializers.Serializer):
    participants = serializers.JSONField()
    deadline = serializers.DateField(allow_null=True, required=False, default=None)
    remark = serializers.JSONField(required=False, 
        allow_null=True, default=None)

    def validate_participants(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('participants must be list')
        return value

    def update(self, instance, validated_data):
        instance.deadline = validated_data.get('deadline', instance.deadline)
        instance.remark = validated_data.get('remark', instance.remark)
        participants = validated_data.get('participants')
        if participants:
            instance.participants.clear()
            for p in participants:
                instance.participants.add(models.Participant.objects.create(executor=p))
        instance.save()
        return instance
    
class WorkflowGetSerializer(serializers.HyperlinkedIdentityField):
    detail = serializers.HyperlinkedIdentityField(
        format='html',
        view_name='template-detail', 
        lookup_field='id')
    # states = serializers.HyperlinkedIdentityField(format='html', view_name='template-states',
    #     lookup_field='id')
    # transitions = serializers.HyperlinkedIdentityField(format='html', 
    #     view_name='template-transitions', lookup_field='id')
    # status = serializers.HyperlinkedIdentityField(format='html', view_name='template-status',
    #     lookup_field='id')

    class Meta:
        model = models.Workflow
        fields = ('id', 'name', 'description', 'creator', 'token',
            'detail')
        #, 'states', 'transitions', 'status')

class WorkflowSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Workflow
        fields = ('id', 'name', 'description', 'status', 'created_on', 'creator', 'token')

class WorkflowDetailSerializer(serializers.ModelSerializer):
    states = StateDetailSerializer(many=True)
    transitions = TransitionPostSerializer(many=True)
    class Meta:
        model = models.Workflow
        fields = ('id', 'name', 'description', 'status', 'created_on', 'creator', 'token',
            'states', 'transitions')


class StatusSerializer(myserializers.Serializer):
    status = serializers.ChoiceField(models.Workflow.STATUS_CHOICE_LIST)



class RecordSerializer(serializers.ModelSerializer):
    participant = ParticipantSerializer()
    class Meta:
        model = models.Record
        fields = ('id', 'participant', 'action', 'note', 'attachment', 'log_on')


class WorkflowHistorySerializer(serializers.ModelSerializer):
    state = StateSimpleSerializer()
    records = RecordSerializer(many=True)
    class Meta:
        model = models.WorkflowHistory
        fields = ('id', 'state', 'status', 'records')


class WorkflowActivityPostSerializer(myserializers.ModelSerializer):
    class Meta:
        model = models.WorkflowActivity
        fields = ('id', 'name', 'description', 'subject', 'workflow', 'creator', 
            'plan_start_time', 'deadline')
    def create(self, validated_data):
        workflow = validated_data['workflow']
        if workflow.status != models.Workflow.ACTIVE:
            raise ValidationError('Only active workflow can create WorkflowActivity')
        if workflow.cloned_from:
            workflow_copy = workflow
        else:
            workflow_copy = workflow.clone(validated_data.get('creator'))
        validated_data['workflow'] = workflow_copy
        return super(WorkflowActivityPostSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get('workflow'):
            del validated_data['workflow']
        return super(WorkflowActivityPostSerializer, self).update(instance, validated_data)

class WorkflowActivitySimpleSerializer(serializers.ModelSerializer):
    workflow = WorkflowSimpleSerializer()
    class Meta:
        model = models.WorkflowActivity
        fields = ('id', 'status', 'name', 'description', 'subject', 'workflow',
            'creator', 'plan_start_time', 'deadline', 'completed_on', 'real_start_time')

    def to_representation(self, instance):
        ret = super(WorkflowActivitySimpleSerializer, self).to_representation(instance)
        if instance.status == instance.EXECUTE:
            current_states = instance.current_state()
            print current_states
            ret['current'] = StateSimpleSerializer(current_states, many=True).data
            # if current_state.state_type!=models.State.END_STATE:
            #     next_state = instance.workflow.states.get(sequence=current_state.sequence+1)
            #     next_state_detail = StateDetailSerializer(next_state).data
            #     ret['next'] = {}
            #     ret['next']['state'] = next_state_detail['name']
            #     ret['next']['executors'] = next_state_detail['participants']
            #     ret['next']['sequence'] = next_state_detail['sequence']            
            #     ret['next']['id'] = next_state_detail['id']            
        else:
            ret['current'] = None
        return ret

class WorkflowActivityDetailSerializer(WorkflowActivitySimpleSerializer):
    workflow = WorkflowDetailSerializer()
    history = WorkflowHistorySerializer(many=True)

    class Meta:
        model = models.WorkflowActivity
        fields = ('id', 'status', 'name', 'description', 'subject', 'workflow',
        'creator', 'plan_start_time', 'deadline', 'completed_on', 'real_start_time', 
        'history')

class CreatorSerializer(serializers.Serializer):
    creator = serializers.JSONField(allow_null=True, required=False, default=None)

class LogeventSerializer(serializers.Serializer):
    state = serializers.IntegerField()
    executor = serializers.JSONField()
    action = serializers.CharField()
    note = serializers.CharField(allow_blank=True, allow_null=True,
        style={'base_template': 'textarea.html'})
    attachment = serializers.JSONField(allow_null=True, required=False, default=None)
    

class WorkflowInputSerializer(myserializers.Serializer):
    filename = serializers.FileField(help_text='only .py file allowed')

    def handle_uploaded_file(self, f):
        filename = 'template' + str(int(time.time()))
        destination = open('./workflow/'+filename+'.py', 'wb+')
        for chunk in f.chunks():
            destination.write(chunk)
        destination.close()
        return filename

    def validate_filename(self, value):
        param = str(value).split('.')
        if param[-1] != 'py':
            raise serializers.ValidationError('only .py file accepted')
        filename = self.handle_uploaded_file(value)
        return filename


class WorkflowSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default=None)
    creator = serializers.CharField(required=False, allow_blank=True, default=None)
    token = serializers.CharField(required=False, allow_blank=True, default=None)
    template = serializers.BooleanField()

class StateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default=None)
    allow_delegation = serializers.BooleanField()
    allow_abolish = serializers.BooleanField()
    allow_state_edit = serializers.BooleanField()
    deadline_warning = serializers.BooleanField()
    participants = serializers.ListField(allow_null=True, default=[], 
        help_text='This field must be list, and each element must be json string')
    auto_end = serializers.BooleanField(required=False, default=False, 
        help_text='if you are use sequence to control workflow, exclude this field, \
        otherwise include this field')
    remark = serializers.CharField(required=False, allow_blank=True, default=None)
    
class TransitionSerializer(serializers.Serializer):
    name = serializers.CharField()
    from_state = serializers.CharField()
    to_state = serializers.CharField()
    callback = serializers.CharField(required=False, allow_blank=True, default=None)
    condition = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    
    def validate_callback(self, value):
        try:
            if value:
                value = json.loads(value)
        except:
            raise ValidationError('must be type of json string')

class WorkflowWholeParamSerializer(serializers.Serializer):
    workflow = WorkflowSerializer()
    states = StateSerializer(many=True, required=True)
    transitions = TransitionSerializer(many=True, required=True)

    def create(self, validated_data):
        from workflow import functions
        return functions.create_workflow(self.data, validated_data['creator'])        


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.State

    def to_representation(self, instance):
        ret = {}
        ret['state'] = StateDetailSerializer(instance).data
        ret['workflowactivity'] = WorkflowActivitySimpleSerializer(
            instance.workflow.workflowactivity).data
        return ret
