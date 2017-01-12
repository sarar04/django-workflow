from django.contrib import admin

from models import *

class WorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'cloned_from')
    list_filter = ('cloned_from', 'belong_to')
    ordering = ('cloned_from',)

class TransitionAdmin(admin.ModelAdmin):
    list_filter = ('workflow',)

class StateAdmin(admin.ModelAdmin):
    list_filter = ('workflow',)

class HistoryAdmin(admin.ModelAdmin):
    list_filter = ('workflowactivity',)


admin.site.register(Workflow, WorkflowAdmin)
admin.site.register(WorkflowActivity)
admin.site.register(Participant)
admin.site.register(State, StateAdmin)
admin.site.register(Transition, TransitionAdmin)
admin.site.register(Record)
admin.site.register(WorkflowHistory, HistoryAdmin)