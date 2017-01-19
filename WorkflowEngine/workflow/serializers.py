# !/usr/bin/env python
# -*- coding: utf-8 -*-

import json, time
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers
from rest_framework.serializers import ValidationError

from workflow import models
from workflow import myserializers

class ParticipantSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Participant
        fields = ('id', 'executor')

class ParticipantSerializer(serializers.ModelSerializer):
    delegate_to = ParticipantSimpleSerializer()
    class Meta:
        model = models.Participant
        fields = ('id', 'executor', 'delegate_to', 'delegate_on')

class StateSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, read_only=True)
    class Meta:
        model = models.State
        fields = ('id', 'name', 'description', 'state_type', 'workflow', 
            'allow_delegation', 'allow_abolish', 'allow_state_edit', 
            'deadline_warning', 'participants', 'deadline', 'auto_end', 'remark')
        extra_kwargs = {'participants': {'read_only': True}}
        read_only_fields = ('workflow', 'participants')

    def to_representation(self, instance):
        ret = super(StateSerializer, self).to_representation(instance)
        ret['actions'] = instance.get_actions()
        ret['status'] = instance.get_status()
        return ret

class TransitionModelSerializer(myserializers.ModelSerializer):
    class Meta:
        model = models.Transition
        fields = ('id', 'name', 'from_state', 'to_state', 'callback', 'condition')

class WorkflowSerializer(myserializers.ModelSerializer):
    class Meta:
        model = models.Workflow
        fields = ('id', 'name', 'description', 'status', 'creator', 'token', 'created_on')
        read_only_fields = ('created_on',)

class WorkflowDetailSerializer(myserializers.ModelSerializer):
    states = StateSerializer(many=True)
    transitions = TransitionModelSerializer(many=True)
    class Meta:
        model = models.Workflow
        fields = ('id', 'name', 'description', 'status', 'creator', 'token', 'created_on', 
            'states', 'transitions')

class StatusSerializer(myserializers.Serializer):
    status = serializers.ChoiceField(models.Workflow.STATUS_CHOICE_LIST)

class TransitionSerializer(serializers.Serializer):
    name = serializers.CharField()
    from_state = serializers.CharField()
    to_state = serializers.CharField()
    callback = serializers.JSONField(allow_null=True, required=False)
    condition = serializers.JSONField(allow_null=True, required=False)
class WorkflowWholeParamSerializer(serializers.Serializer):
    workflow = WorkflowSerializer()
    states = StateSerializer(many=True, required=True)
    transitions = TransitionSerializer(many=True, required=True)
    template = serializers.BooleanField()

    def create(self, validated_data):
        from workflow import functions
        print validated_data['belong_to']
        print validated_data['workflow']
        return functions.create_workflow_wholeparam(validated_data, validated_data['belong_to'])        

class WorkflowFileSerializer(myserializers.Serializer):
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

class StateSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.State
        fields = ('id', 'name')
class WorkflowActivitySimpleSerializer(serializers.ModelSerializer):
    workflow = WorkflowSerializer()
    class Meta:
        model = models.WorkflowActivity
        fields = ('id', 'status', 'name', 'description', 'subject', 'workflow',
            'creator', 'plan_start_time', 'deadline', 'completed_on', 'real_start_time')

    def to_representation(self, instance):
        ret = super(WorkflowActivitySimpleSerializer, self).to_representation(instance)
        if instance.status == instance.EXECUTE:
            current_states = instance.current_state()
            ret['current'] = StateSimpleSerializer(current_states, many=True).data
        else:
            ret['current'] = None
        return ret

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

class LogeventSerializer(serializers.Serializer):
    state = serializers.IntegerField()
    executor = serializers.JSONField()
    action = serializers.CharField()
    note = serializers.CharField(allow_blank=True, allow_null=True,
        style={'base_template': 'textarea.html'})
    attachment = serializers.JSONField(allow_null=True, required=False, default=None)

class DelegateSerializer(serializers.Serializer):
    state = serializers.IntegerField()
    executor = serializers.JSONField()
    delegator = serializers.JSONField()
    note = serializers.CharField()
    attachment = serializers.JSONField(allow_null=True, required=False, default=None)
    repeat = serializers.BooleanField()

class TaskSerializer(StateSerializer):
    def to_representation(self, instance):
        ret = {}
        ret['state'] = StateSerializer(instance).data
        ret['workflowactivity'] = WorkflowActivitySimpleSerializer(
            instance.workflow.workflowactivity).data
        return ret