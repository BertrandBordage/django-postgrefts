# coding: utf-8

from __future__ import unicode_literals
from optparse import make_option
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand
from django.db.models import get_models, get_app, get_model
from ...models import Index
from ...registry import search_registry


class Command(BaseCommand):
    help = 'Updates PostgreSQL index'
    args = '[app_label[.modelname] [...]]'
    option_list = BaseCommand.option_list + (
        make_option('-l', '--language', action='append', dest='languages',
                    type='choice', choices=[t[0] for t in settings.LANGUAGES],
                    help='Language code to index (indexes all by default).'),
        make_option('-r', '--rebuild', action='store_true', dest='rebuild',
                    default=False,
                    help='Deletes all entries before rebuilding index'),
        make_option('-b', '--batch-size', action='store', dest='batch_size',
                    default=None, type='int',
                    help='Number of items to index at once.'),
    )
    leave_locale_alone = True

    def handle(self, *args, **options):
        update_kwargs = {
            'languages': options['languages'],
            'rebuild': options['rebuild'],
        }

        if args:
            models = []
            for arg in args:
                try:
                    app = get_app(arg)
                except ImproperlyConfigured:
                    app_label = '.'.join(arg.split('.')[:-1])
                    model_name = arg.split('.')[-1]
                    models.append(get_model(app_label, model_name))
                else:
                    models.extend([m for m in get_models(app)
                                   if m in search_registry])
            update_kwargs['models'] = models

        if options['batch_size'] is not None:
            assert options['batch_size'] > 0
            update_kwargs['batch_size'] = options['batch_size']

        Index.objects.update_index(**update_kwargs)
