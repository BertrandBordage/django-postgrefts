# coding: utf-8

from __future__ import unicode_literals
from django.conf.urls import patterns, url
from .views import AutocompleteView, SearchView


urlpatterns = patterns('',
    url(r'^autocomplete/$', AutocompleteView.as_view(), name='autocomplete'),
    url(r'^$', SearchView.as_view(), name='search'),
)
