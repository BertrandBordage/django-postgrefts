# coding: utf-8

from __future__ import unicode_literals
import json
from django.http import HttpResponse
from django.views.generic import View, ListView
from .models import Index
from .registry import search_registry


class AutocompleteView(View):
    model = Index
    key = 'term'
    max_results = 5
    models = None

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.key not in self.request.GET:
            return qs.none()

        if self.models is None:
            qs = qs.for_models(*[m for m, sm in search_registry.items()
                                 if sm.in_global_autocomplete])
        else:
            qs = qs.for_models(*self.models)
        return qs.autocomplete(
            self.request.GET[self.key], sort=True
        ).values_list('title', flat=True)[:self.max_results]

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return HttpResponse(json.dumps(list(qs)),
                            content_type='application/json')


class SearchView(ListView):
    model = Index
    key = 'q'
    template_name = 'postgrefts/search.html'

    def get_queryset(self):
        qs = super(SearchView, self).get_queryset()
        if self.key not in self.request.GET:
            return qs.none()

        qs = qs.for_models(*[m for m, sm in search_registry.items()
                             if sm.in_global_search])
        q = self.request.GET[self.key]
        return qs.search(q, sort=True)

    def get_context_data(self, **kwargs):
        context = super(SearchView, self).get_context_data(**kwargs)
        context['query'] = self.request.GET.get(self.key, '')
        return context
