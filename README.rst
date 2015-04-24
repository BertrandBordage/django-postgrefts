Django-PostgreFTS
=================

**Please don’t use this project. It’s just a prototype**

Installation
------------

- Run ``pip install https://github.com/BertrandBordage/django-postgrefts/archive/master.tar.gz``
- Add ``'postgrefts',`` to ``INSTALLED_APPS``

Example usage with django CMS
-----------------------------

In a `search_meta.py` file in an application registered in ``INSTALLED_APPS``,
write:

.. code-block:: python

    from cms.models import Title
    from django.utils import translation
    from postgre_fts.registry import search_registry, ModelSearchMeta


    @search_registry.add
    class TitleSearchMeta(ModelSearchMeta):
        model = Title
        select_relateds = ('page',)
        prefetch_relateds = ('page__placeholders__cmsplugin_set',)

        def get_queryset(self):
            return self.model.objects.public().filter(
                page__in_navigation=True,
                page__level__gt=1,
                language=translation.get_language())

        def get_title(self, obj):
            return obj.title

        def get_absolute_url(self, obj):
            return obj.page.get_absolute_url()

        def get_boost(self, obj):
            return 5.0 / (obj.page.level + 1)

        def get_image(self, obj):
            from .models import CMSPageExtra
            thumbnail = None
            try:
                thumbnail = obj.cmspageextra.thumbnail
            except CMSPageExtra.DoesNotExist:
                pass
            if not thumbnail:
                try:
                    thumbnail = obj.publisher_draft.cmspageextra.thumbnail
                except CMSPageExtra.DoesNotExist:
                    pass
            return thumbnail


In a `templates/cms/indexes/title_body.txt` in the same application:

.. code-block:: django

    {% autoescape off %}
      {{ object.meta_description|default_if_none:'' }}
      {% for tag in object.tags.all %}
        {{ tag }}
      {% endfor %}

      {% for placeholder in object.page.placeholders.all %}
        {% for plugin in placeholder.cmsplugin_set.all %}
          {% with plugin_instance=plugin.get_plugin_instance.0 %}
            {{ plugin_instance.body }}
          {% endwith %}
        {% endfor %}
      {% endfor %}
    {% endautoescape %}

Then, you can rebuild index using `./manage.py update_index`.

Query examples
--------------

.. code-block:: python

    from postgrefts.models import Index

    Index.objects.all()                       # All results
    Index.objects.for_language()              # All results for the current languages
    Index.objects.for_language('fr')          # All results in French
    Index.objects.for_models(Title, Person)   # All results for the given models
    Index.objects.search('I <3 Django')       # Simple search
    Index.objects.autocomplete('Postg')       # Returns all results starting with this
    Index.objects.search('Marion', sort=True) # Same as search, but sorts results
    Index.objects.autocomplete('Don Giov', sort=True)
    Index.objects.search('Pur ti miro').highlight()  # Highlight query in the results’ body

    # Full example
    Index.objects.for_language().for_models(Language) \
        .search('Python', sort=True).highlight()[:5]
