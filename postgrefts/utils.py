# coding: utf-8

from __future__ import unicode_literals


def get_model_repr(model_or_object):
    return '%s.%s' % (model_or_object._meta.app_label,
                      model_or_object._meta.model_name)
