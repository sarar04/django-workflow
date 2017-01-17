# !/usr/bin/env python
# -*- coding: utf-8 -*-
import logging, subprocess

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db.models import Q

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError

from . import serializers, functions, models

from error_list import error_list
from errors import BadRequest, Http403

logger = logging.getLogger('workflowapp')

class WorkflowListView(generics.ListCreateAPIView):
    """
    get: 获取工作流模板     
    get时可以带后缀 ?status=2 ([0 or 1 or 2]) 通过status值过滤不同状态的模板 

    post: 分步模式创建工作流模板     
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.Workflow.objects.all()
    serializer_class = serializers.WorkflowPostSerializer
    
    def get_queryset(self):
        queryset = models.Workflow.objects.filter(
            belong_to=self.request.user,
            cloned_from=None)
        query=self.request.GET.get('status', -1)
        if query!=-1:
            return queryset.filter(status=query)
        return queryset

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowSimpleSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        serializer.save(belong_to=self.request.user)

class WorkflowWholeparameterView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = []
    serializer_class = serializers.WorkflowWholeParamSerializer

    def get(self, request, *args, **kwargs):
        """
        获取参数示例,后缀含有_json的字段,若非空建议用json字符串
        # callback_json若非空则必须为json字符串,会做格式检查
        ---
        omit_serializer: true
        """
        from templates.flow_templates.sequence import data
        return Response(data)

    def post(self, request, *args, **kwargs):
        """
        完整参数模式创建工作流模板: 参数格式见get方法返回结果     
        # callback_json若非空则必须为json字符串,会做格式检查
        ---
        omit_serializer: true
        """
        return Execute_func(functions.create_workflow_wholeparam(request.data))

        serializer = serializers.WorkflowWholeParamSerializer(data=request.data)
        if not serializer.is_valid():
            raise BadRequest(error_list['parameter_error'], serializer.errors)
        workflow = serializer.save(creator=request.user)
        serializer = serializers.WorkflowDetailSerializer(workflow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class WorkflowFileView(generics.ListCreateAPIView):
    """上传导入方式创建工作流模板"""
    permission_classes = (IsAuthenticated,)
    queryset = []
    serializer_class = serializers.WorkflowInputSerializer

    def file_iterator(self, file_name, chunk_size=512):
        with open(file_name) as f:
          while True:
            c = f.read(chunk_size)
            if c:
              yield c
            else:
              break

    def get(self, request, *args, **kwargs):
        """获取上传文件模板 """
        import os
        from django.http import StreamingHttpResponse

        if request.GET.get('download'):
            file_name_full =  'workflow/templates/flow_templates/'+request.GET['download']+'.py'
            file_path, file_name = os.path.split(file_name_full)
            response = StreamingHttpResponse(self.file_iterator(file_name_full))
            response['Content-Type'] = 'application/octet-stream'
            response['Content-Disposition'] = 'attachment;filename="{0}"'.format(file_name)
            return response
        else:
            url = 'http://localhost:'+str(request.META['SERVER_PORT'])+request.path
            data = {
                u'点击下载线性流程模板': url+'?download=sequence',
                u'点击下载分支流程模板': url+'?download=branch'
            }
        return Response(data)

    def post(self, request, *args, **kwargs):
        """上传.py文件导入模板"""
        serializer = serializers.WorkflowInputSerializer(data=request.data)
        if not serializer.is_valid():
            raise BadRequest(error_list['parameter_error'], serializer.errors)
        validated_data = serializer.validated_data
        workflow = functions.create_workflow_by_file(validated_data['filename'], self.request.user)
        serializer = serializers.WorkflowDetailSerializer(workflow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class WorkflowDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    流程模板详情: retrieve, update or delete
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.Workflow.objects.all()
    serializer_class = serializers.WorkflowPostSerializer
    # lookup_field = 'id'

    def get_queryset(self):
        return models.Workflow.objects.filter(
            belong_to=self.request.user,
            cloned_from=None)
    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowDetailSerializer
        return self.serializer_class

    def check_permission(self, instance):
        if instance.status != models.Workflow.DEFINITION:
            raise BadRequest(error_list['only_definition_allowed'])
        if instance.cloned_from:
            raise BadRequest(error_list['only_template_allowed'])
        if instance.belong_to != self.request.user:
            raise Http403('Only belong_to user can modified')

    def perform_update(self, serializer):
        instance = self.get_object()
        self.check_permission(instance)
        instance = serializer.save()

    def perform_destroy(self, instance):
        self.check_permission(instance)
        instance.delete()

class WorkflowDetailPngView(generics.RetrieveAPIView):
    """
    流程模板预览：图片方式预览流程的节点和流转方向
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.Workflow.objects.all()
    serializer_class = serializers.WorkflowDetailSerializer

    def get(self, request, *args, **kwargs):
        workflow = self.get_object()
        current_state = None
        try:
            if workflow.workflowactivity.status==models.WorkflowActivity.EXECUTE:
                current_state = workflow.workflowactivity.current_state().state
        except:
            pass
        proc = subprocess.Popen('%s -Tpng ' % 'dot',
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        response = HttpResponse(content_type='image/png')
        response.write(proc.communicate(functions.get_dotfile(workflow, 
            current_state).encode('utf8'))[0])
        return response


class StateListView(generics.ListCreateAPIView):
    """
    通过流程pk获取流程的所有节点详情
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.State.objects.all()
    serializer_class = serializers.StatePostSerializer

    def get_queryset(self):
        return models.State.objects.filter(workflow__id=int(self.kwargs['pk']))

    def perform_create(self, serializer):
        instance = get_object_or_404(models.Workflow, pk=int(self.kwargs['pk']))
        if instance.cloned_from:
            raise BadRequest(error_list['only_template_allowed'])
        if instance.status != instance.DEFINITION:
            raise BadRequest(error_list['only_definition_allowed'])
        if instance.belong_to!=self.request.user:
            raise Http403('Only belong_to user can modified')
        serializer.save(workflow=instance)

class StateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    流程节点详情：retrieve, update, delete
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.State.objects.all()
    serializer_class = serializers.StatePostSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.StateDetailSerializer
        return self.serializer_class

    def check_permission(self, instance):
        if instance.workflow.status != models.Workflow.DEFINITION:
            raise BadRequest(error_list['only_definition_allowed'])
        if instance.workflow.cloned_from:
            raise BadRequest(error_list['only_template_allowed'])
        if instance.workflow.belong_to != self.request.user:
            raise Http403('Only belong_to user can modified')        

    def perform_update(self, serializer):
        instance = self.get_object()
        self.check_permission(instance)
        return super(StateDetailView, self).perform_update(serializer)

    def perform_destroy(self, instance):
        self.check_permission(instance)
        return super(StateDetailView, self).perform_destroy(instance)

class TransitionListView(generics.ListCreateAPIView):
    """
    get: 通过流程pk获取流程的所有流转方向详情       
    post: 为workflow创建流转方向(transition)
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.Transition.objects.all()
    serializer_class = serializers.TransitionPostSerializer

    def get_queryset(self):
        return models.Transition.objects.filter(workflow__id=self.kwargs['pk'])

    def perform_create(self, serializer):
        instance = get_object_or_404(models.Workflow, pk=int(self.kwargs['pk']))
        from_state = serializer.validated_data['from_state']
        to_state = serializer.validated_data['to_state']
        if from_state.workflow!=instance or to_state.workflow!=instance:
            raise BadRequest(error_list['state_workflow_not_match'])
        if instance.cloned_from:
            raise BadRequest(error_list['only_template_allowed'])
        if instance.status != instance.DEFINITION:
            raise BadRequest(error_list['only_definition_allowed'])
        if instance.belong_to!=self.request.user:
            raise Http403('Only belong_to user can modified')
        serializer.save(workflow=instance)

class TransitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    流转方向详情：retrieve, update, delete
    """
    permission_classes = (IsAuthenticated,)
    queryset = models.Transition.objects.all()
    serializer_class = serializers.TransitionPostSerializer

    def check_permission(self, instance):
        if instance.workflow.status != models.Workflow.DEFINITION:
            raise BadRequest(error_list['only_definition_allowed'])
        if instance.workflow.cloned_from:
            raise BadRequest(error_list['only_template_allowed'])
        if instance.workflow.belong_to != self.request.user:
            raise Http403('Only belong_to user can modified')        

    def perform_update(self, serializer):
        instance = self.get_object()
        self.check_permission(instance)
        return super(TransitionDetailView, self).perform_update(serializer)

    def perform_destroy(self, instance):
        self.check_permission(instance)
        return super(TransitionDetailView, self).perform_destroy(instance)


class WorkflowStatusView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.Workflow.objects.all()
    serializer_class = serializers.StatusSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowSimpleSerializer
        return self.serializer_class

    def perform_update(self, serializer):
        from functions import change_workflow_status
        instance = self.get_object()
        if instance.cloned_from:
            raise BadRequest(error_list['only_template_allowed'])
        if instance.belong_to != self.request.user:
            raise Http403('only belong_to user can modified')

        success, instance = change_workflow_status(
            wf_instance=instance,
            oldstatus=instance.status,
            newstatus=self.request.data['status'])
        if not success:
            raise ValidationError(instance)



class WorkflowActivityListView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.WorkflowActivityPostSerializer

    def get_queryset(self):
        queryset = models.WorkflowActivity.objects.filter(
            workflow__belong_to=self.request.user)
        query = self.request.GET.get('status', -1)
        executor_json = self.request.GET.get('executor_json')
        search = self.request.GET.get('search')
        if query!=-1:
            queryset = queryset.filter(status=query)
        if executor_json:
            queryset = queryset.filter(history__records__participant__executor_json=executor_json)
        if search:
            queryset = queryset.filter(Q(name__contains=search) | 
                Q(real_start_time__contains=search) |
                Q(completed_on__contains=search))
        return queryset.distinct().order_by('-completed_on')

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivitySimpleSerializer
        return self.serializer_class

class WorkflowActivityDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.WorkflowActivityPostSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivityDetailSerializer
        return self.serializer_class

class WorkflowActivityStateListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = []
    serializer_class = serializers.StateDetailSerializer

    def get_queryset(self):
        return models.State.objects.filter(
            workflow__workflowactivity__id=int(self.kwargs['pk']))

class WorkflowActivityStateDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.State.objects.all()
    serializer_class = serializers.StateDetailSerializer

    def put(self, request, ppk, pk):
        instance = self.get_object()
        serializer = serializers.WorkflowActivityStatePatchSerializer(
            data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(instance, serializer.validated_data)
        return Response(serializers.StateDetailSerializer(instance).data)
    # def get_serializer_class(self):
    #     if self.request.method!='GET':
    #         return serializers.WorkflowActivityStatePatchSerializer
    #     return serializers.StateDetailSerializer

    # def perform_update(self, serializer):
    #     instance = self.get_object()
    #     if instance.workflow.workflowactivity.status>=models.WorkflowActivity.ABOLISHED:
    #         raise ValidationError('wrong status, cannot edit')
    #     return super(WorkflowActivityStateDetailView, self).perform_update(serializer)

class WorkflowActivityTransitionListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = []
    serializer_class = serializers.TransitionPostSerializer

    def get_queryset(self):
        return models.Transition.objects.filter(
            workflow__workflowactivity__id=int(self.kwargs['pk']))


class WorkflowActivityCommitView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.CreatorSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivityDetailSerializer
        return self.serializer_class

    def perform_update(self, serializer):
        instance = self.get_object()
        success, result = instance.commit(self.request.data.get('creator'))
        if not success:
            raise ValidationError('commit faild')

class WorkflowActivityStartView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.CreatorSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivityDetailSerializer
        return self.serializer_class

    def perform_update(self, serializer):
        instance = self.get_object()
        success, result = instance.start(self.request.data.get('creator'))
        if not success:
            raise BadRequest(result)

class WorkflowActivityLogeventView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.LogeventSerializer
    pass_flag = True

    def get_object(self):
        instance = get_object_or_404(models.WorkflowActivity, pk=int(self.kwargs['pk']))
        return instance

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivityDetailSerializer
        return self.serializer_class

    def get(self, request, *arg, **kwargs):
        instance = self.get_object()
        serializer = serializers.WorkflowActivityDetailSerializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        instance = self.get_object()
        validated_data = serializer.validated_data
        state = instance.workflow.states.filter(pk=serializer.data['state'])
        if state:
            validated_data['state'] = state[0]
            success, result = instance.log_event(**validated_data)
            if not success:
                raise ValidationError(result)
        else:
            raise BadRequest(error_list['parameter_error'])
        # data = request.data
        # success, result, progress = functions.logevent(wa_instance=instance, 
        #     executor_json=data['executor_json'], pass_flag=self.pass_flag, 
        #     note=data['note'], attachment_json=data['attachment_json'], 
        #     condition_json=data.get('condition_json', 'no_condition_json'))
        # if not success:
        #     raise BadRequest(result)
        # instance = self.get_object()
        # serializer = serializers.WorkflowActivityDetailSerializer(instance)
        # data = serializer.data
        # return Response(data, status=status.HTTP_201_CREATED)

class WorkflowActivityRejectView(WorkflowActivityLogeventView):
    pass_flag = False

class WorkflowActivityAbolishView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.CreatorSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivityDetailSerializer
        return self.serializer_class

    def perform_update(self, serializer):
        instance = self.get_object()
        success, result = instance.abolish(self.request.data)
        if not success:
            raise ValidationError('abolish faild')

class WorkflowActivityDelegateView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.WorkflowSimpleSerializer

    def get_object(self):
        instance = models.WorkflowActivity.objects.get(pk=self.kwargs['pk'])
        return instance

    def get(self, request, *arg, **kwargs):
        instance = self.get_object()
        serializer = serializers.WorkflowActivityDetailSerializer(instance)
        return Response(serializer.data)

    def post(self, request, *arg, **kwargs):
        instance = self.get_object()
        executor_json = request.data.get('executor_json')
        delegator_json = request.data.get('delegator_json')
        reason = request.data.get('reason')
        attachment_json = request.data.get('attachment_json')

        if not delegator_json or not executor_json:
            msg = 'executor_json and delegator_json need'
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
        succ, result = instance.delegation(user_json=executor_json,
            delegator_json=delegator_json, reason=reason, 
            attachment_json=attachment_json)
        if not succ:
            raise BadRequest(result)
        instance = self.get_object()
        serializer = serializers.WorkflowActivityDetailSerializer(instance)
        return Response(serializer.data)

class ParticipantTaskView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = []
    serializer_class = serializers.WorkflowActivitySimpleSerializer

    def get(self, request, *arg, **kwargs):
        executor_json = self.request.GET.get('executor_json')
        if not executor_json:
            return Response('executor_json need', status=status.HTTP_400_BAD_REQUEST)
        tasks = functions.get_participant_task_data(executor_json, request.user)
        return Response(tasks)

class HistoryPngView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.WorkflowActivityDetailSerializer

    def get(self, request, *args, **kwargs):
        workflowactivity = self.get_object()
        histories = workflowactivity.history.all().order_by('created_on')
        proc = subprocess.Popen('%s -Tpng ' % 'dot',
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        response = HttpResponse(content_type='image/png')
        response.write(proc.communicate(functions.get_history_dotfile(histories).encode('utf8'))[0])
        return response

# ---------------------------------------------------------------------------
class WorkflowActivityStatusView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = models.WorkflowActivity.objects.all()
    serializer_class = serializers.StatusSerializer

    def get_serializer_class(self):
        if self.request.method=='GET':
            return serializers.WorkflowActivitySimpleSerializer
        return self.serializer_class

    def perform_update(self, serializer):
        from functions import change_workflowactivity_status
        instance = self.get_object()

        success, instance = change_workflowactivity_status(
            wa_instance=instance,
            oldstatus=instance.status,
            newstatus=self.request.data['status'])
        if not success:
            raise ValidationError(instance)