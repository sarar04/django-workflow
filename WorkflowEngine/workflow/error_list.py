# !/usr/bin/env python
# -*- coding: utf-8 -*-

error_list = {
    # these error occur in workflow.models
    # error index                             error code      error detail
    'only_creator_allowed'          :         ['400001',      'Only creator allowed'],
    'only_edit_allowed'             :         ['400002',      'Only EDIT status allowed'],
    'only_commit_allowed'           :         ['400003',      'Only COMMIT status allowed'],
    'multi_start_state'             :         ['400004',      'Multiple start state'],  # 流程有且只有一个起始节点
    'next_state_pant_needed'        :         ['400005',      'Participant of next state needed'], 
    'only_progress_allowed'         :         ['400006',      'Only PROGRESS status allowed'],
    'invalid_transition'            :         ['400007',      'Invalid transition when progress'],
    'reject_denied'                 :         ['400008',      'Reject not allowed'],   # 节点不允许退回
    'repeated_logevent'             :         ['400009',      'Repeated logevent'],    # 重复提交任务
    'delegate_denied'               :         ['400010',      'Delegate denied'],      # 节点不允许委托
    'invalid_executor'              :         ['400011',      'Invalid executor'],     # 非法的任务执行者
    'delegate_only_once'            :         ['400012',      'Delegate only once'],   # 节点每个执行人最多委托一次
    'invalid_delegator'             :         ['400013',      'Invalid delegator'],    # 非法的委托人(不能委托给当前节点的执行人)
    'abolish_denied'                :         ['400014',      'Abolish denied'],       # 节点不允许废止
    'edit_state_denied'             :         ['400015',      'Edit state denied'],
    'only_follow_up_allowed'        :         ['400016',      'Only follow-up state can be edited'],
    'only_definition_allowed'       :         ['400017',      'Only DEFINITION status allowed'],
    'next_state_participant_needed' :         ['400018',      'Participants of next state needed'],   # 提交任务前请设置下一节点执行人
    'only_template_allowed'         :         ['400019',      'Only workflow template allowed to modify'],
    'parameter_error'               :         ['400020',      'Parameter error, see doc for help'],   # 参数错误
    'state_workflow_not_match'      :         ['400021',      'Create transition between from_state and to_state which not match workflow'],
    'invalid_condition_json'        :         ['400022',      'Invalid condition json, workflow cannot route'], # 流转条件错误
}