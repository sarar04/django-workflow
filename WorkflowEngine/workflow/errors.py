# !/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, sys

from rest_framework import exceptions, status
from django.utils.translation import ugettext_lazy as _, ungettext

logger = logging.getLogger('workflow')

class BadRequest(exceptions.ValidationError):
    detail = {}
    default_error = _('Bad request.')

    def __init__(self, error_list, detail=None):

        self.detail['error_num'] = error_list[0]
        self.detail['error_msg'] = error_list[1]
        self.detail['detail'] = detail
        logger.info(error_list)

class ResponseModel(exceptions.ValidationError):
    detail = {}
    default_error = _('Bad request.')

    def __init__(self, detail=None, error=None):
        if error is not None:
            self.detail['error'] = error
        else:
            self.detail['error'] = self.default_error
        self.detail['detail'] = detail
        logger.info('func: %s line: %d' % (sys._getframe().f_back.f_code.co_name, 
            sys._getframe().f_back.f_lineno))

class Http500(ResponseModel):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_error = _('Internal server error.')

class Http404(ResponseModel):
    status_code = status.HTTP_404_NOT_FOUND
    default_error = _('Not found.')

class Http403(ResponseModel):
    status_code = status.HTTP_403_FORBIDDEN
    default_error = _('Forbidden.')