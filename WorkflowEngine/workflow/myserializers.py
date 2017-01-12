# -*- coding: utf-8 -*-

from rest_framework import serializers
from rest_framework.serializers import ValidationError

from errors import BadRequest
from error_list import error_list

class ModelSerializer(serializers.ModelSerializer):
    def is_valid(self, raise_exception=False):
        try:
            return super(ModelSerializer, self).is_valid(raise_exception)
        except Exception, e:
            raise BadRequest(error_list['parameter_error'], str(e))

class Serializer(serializers.Serializer):
    def is_valid(self, raise_exception=False):
        try:
            return super(Serializer, self).is_valid(raise_exception)
        except Exception, e:
            raise BadRequest(error_list['parameter_error'], str(e))
    