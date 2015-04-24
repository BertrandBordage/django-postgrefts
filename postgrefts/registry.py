# coding: utf-8

from __future__ import unicode_literals
import warnings

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.encoding import force_text
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule
from easy_thumbnails.exceptions import InvalidImageFormatError
from easy_thumbnails.files import get_thumbnailer

from .utils import get_model_repr


class Registry(dict):
    module_name = 'search_meta'

    def autodiscover(self):
        for app in settings.INSTALLED_APPS:
            mod = import_module(app)
            try:
                import_module('%s.%s' % (app, self.module_name))
            except:
                if module_has_submodule(mod, self.module_name):
                    raise

    def add(self, cls):
        model = cls.model
        if model is not None:
            self[model] = cls()
        return cls


search_registry = Registry()


class ModelSearchMeta(object):
    model = None
    in_global_autocomplete = True
    in_global_search = True
    boost = 1.0
    select_relateds = ()
    prefetch_relateds = ()
    thumbnail_options = {'size': (128, 128)}

    def get_queryset(self):
        return self.model._default_manager.all()

    def get_absolute_url(self, obj):
        return obj.get_absolute_url()

    def get_boost(self, obj):
        return self.boost

    def get_title(self, obj):
        return force_text(obj)

    def _render_template(self, template_name, context):
        try:
            return render_to_string(template_name, context)
        except TemplateDoesNotExist:
            return ''

    def get_body(self, obj):
        template_name = '%s/indexes/%s_body.txt' % (
            obj._meta.app_label, obj._meta.model_name)
        context = {'object': obj}
        return self._render_template(template_name, context)

    def get_image(self, obj):
        return

    def get_thumbnail_url(self, obj):
        image = self.get_image(obj)
        if image:
            try:
                return get_thumbnailer(image).get_thumbnail(
                    self.thumbnail_options).url
            except (InvalidImageFormatError, IOError) as e:
                warnings.warn(
                    'Could not generate thumbnail for <%s: %d> (%s)'
                    % (get_model_repr(obj), obj.pk, e))
        return ''
