#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.conf.urls import include, url
from django.contrib import admin

from . import views

urlpatterns = [
    # create workflow step by step
    url(r'^workflow/$', views.WorkflowListView.as_view()),
    url(r'^workflow/(?P<pk>[0-9]+)$', views.WorkflowDetailView.as_view(), name="template-detail"),
    url(r'^workflow/(?P<pk>[0-9]+)/state/$', views.StateListView.as_view(), name='template-states'),
    url(r'^state/(?P<pk>[0-9]+)$', views.StateDetailView.as_view()),
    url(r'^workflow/(?P<pk>[0-9]+)/transition/$', views.TransitionListView.as_view(), name='template-transitions'),
    url(r'^transition/(?P<pk>[0-9]+)$', views.TransitionDetailView.as_view()),

    # create workflow at a time
    url(r'^workflow/whole/$', views.WorkflowWholeparameterView.as_view()),
    url(r'^workflow/file/$', views.WorkflowFileView.as_view()),
    
    # change status of workflow
    url(r'^workflow/(?P<pk>[0-9]+)/status/$', views.WorkflowStatusView.as_view(), name='template-status'),
    
    # workflow preview
    # url(r'^workflow/(?P<pk>[0-9]+)/png/$', views.WorkflowDetailPngView.as_view(), name="template-png"),


    url(r'^workflowactivity/$', views.WorkflowActivityListView.as_view()),
    url(r'^workflowactivity/(?P<pk>[0-9]+)$', views.WorkflowActivityDetailView.as_view(), name="instance-detail"),
    
    url(r'^workflowactivity/(?P<ppk>[0-9]+)/state/(?P<pk>[0-9]+)$', views.WorkflowActivityStateDetailView.as_view()),
    
    url(r'^workflowactivity/(?P<pk>[0-9]+)/commit/$', views.WorkflowActivityCommitView.as_view(), name='instance-commit'),
    url(r'^workflowactivity/(?P<pk>[0-9]+)/start/$', views.WorkflowActivityStartView.as_view(), name='instance-start'),
    url(r'^workflowactivity/(?P<pk>[0-9]+)/logevent/$', views.WorkflowActivityLogeventView.as_view(), name='instance-logevent'),
    url(r'^workflowactivity/(?P<pk>[0-9]+)/abolish/$', views.WorkflowActivityAbolishView.as_view(), name='instance-abolish'),
    url(r'^workflowactivity/(?P<pk>[0-9]+)/delegate/$', views.WorkflowActivityDelegateView.as_view(), name='instance-delegate'),
    url(r'^workflowactivity/(?P<pk>[0-9]+)/history/$', views.HistoryPngView.as_view(), name='instance-history'),

    url(r'^participant-task/$', views.ParticipantTaskView.as_view()),

    # url(r'^workflowactivity/(?P<pk>[0-9]+)/state/$', views.WorkflowActivityStateListView.as_view(), name='instance-states'),
    # url(r'^workflowactivity/(?P<pk>[0-9]+)/transition/$', views.WorkflowActivityTransitionListView.as_view(), name='instance-transitions'),
    # url(r'^workflowactivity-state/(?P<pk>[0-9]+)$', views.WorkflowActivityStateDetailView.as_view()),

]