# -*- coding: utf-8 -*-
from collective.documentgenerator.browser.generation_view import DocumentGenerationView
from collective.documentgenerator.helper.dexterity import DXDocumentGenerationHelperView
from collective.taxonomy.interfaces import ITaxonomy
from cpskin.core.interfaces import IFolderViewSelectedContent as IFVSC
from cpskin.locales import CPSkinMessageFactory as _
from plone import api
from plone.app.event.base import date_speller
from plone.app.event.base import dates_for_display
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.component import getSiteManager
from zope.publisher.browser import BrowserView
import json


class FrontPage(BrowserView):

    index = ViewPageTemplateFile('templates/frontpage.pt')


class HelpPage(BrowserView):

    index = ViewPageTemplateFile('templates/helppage.pt')


class OpenData(BrowserView):
    """Get data news, events rss feed and collective.directory csv files."""

    index = ViewPageTemplateFile('templates/opendata.pt')

    def get_links(self):
        portal = api.portal.get()
        links = []
        path = '/'.join(portal.getPhysicalPath())
        portal_catalog = api.portal.get_tool('portal_catalog')
        query_dict = {}
        query_dict['path'] = {'query': path, 'depth': 1}
        query_dict['portal_type'] = ['Folder']
        query_dict['object_provides'] = IFVSC.__identifier__
        query_dict['sort_on'] = 'getObjPositionInParent'
        brains = portal_catalog(query_dict)
        for brain in brains:
            folder = brain.getObject()
            if getattr(folder, 'default_page', None):
                default_page = folder.default_page
                default_obj = folder[default_page]
                rsslink = '{0}/atom.xml'.format(default_obj.absolute_url())
                links.append(rsslink)

        query_dict = {}
        query_dict['portal_type'] = ['collective.directory.directory']
        brains = portal_catalog(query_dict)
        for brain in brains:
            directory = brain.getObject()
            catalog = api.portal.get_tool('portal_catalog')
            query_dict = {}
            query_dict['portal_type'] = 'collective.directory.card'
            query_dict['path'] = {
                'query': '/'.join(directory.getPhysicalPath()), 'depth': 3}
            size = len(catalog(query_dict))
            if size > 3:
                csvlink = '{0}/collective_directory_export_view'.format(
                    directory.absolute_url()
                )
                links.append(csvlink)

        return links


class IDocumentGenerationView(DocumentGenerationView):
    """Override the 'get_generation_context' properly so 'get_base_generation_context'
       is available for sub-packages that want to extend the template generation context."""

    def _get_generation_context(self, helper_view):
        result = super(IDocumentGenerationView, self)._get_generation_context(helper_view)
        view = self.context.restrictedTraverse('faceted_query')
        result['brains'] = view.query(batch=False)
        return result


class EventGenerationHelperView(DXDocumentGenerationHelperView):

    def is_same_month(self, start, end):
        return start.get('month') == end.get('month')

    def get_formatted_date(self):
        date_formated = u''
        event = self.real_context
        dates = dates_for_display(event)
        date_spel_start = date_speller(event, dates.get('start_iso'))
        date_spel_end = date_speller(event, dates.get('end_iso'))
        # day and month
        if dates.get('same_day'):
            date_formated = u'{0} {1}'.format(
                date_spel_start.get('day'),
                date_spel_start.get('month'))
        elif self.is_same_month(date_spel_start, date_spel_end):
            date_formated = u'{0} au {1} {2}'.format(
                date_spel_start.get('day'),
                date_spel_end.get('day'),
                date_spel_start.get('month'))
        else:
            date_formated += u'{0} {1} au {2} {3}'.format(
                date_spel_start.get('day'),
                date_spel_start.get('month'),
                date_spel_end.get('day'),
                date_spel_end.get('month'))

        # hour
        if not dates.get('whole_day'):
            if dates.get('open_end'):
                date_formated += _(u' à ')
                date_formated += u'{0}:{1}'.format(
                    date_spel_start.get('hour'),
                    date_spel_start.get('minute2'))
            else:
                date_formated += _(u' de ')
                date_formated += u'{0}:{1}'.format(
                    date_spel_start.get('hour'),
                    date_spel_start.get('minute2'))
                date_formated += _(u' à ')
                date_formated += u'{0}:{1}'.format(
                    date_spel_end.get('hour'),
                    date_spel_end.get('minute2'))

        return date_formated

    def get_taxonomy_value(self, field_name):
        lang = self.real_context.language
        taxonomy_id = self.get_value(field_name)
        domain = 'collective.taxonomy.{0}'.format(
            field_name.replace('taxonomy_', '').replace('_', ''))

        sm = getSiteManager()
        utility = sm.queryUtility(ITaxonomy, name=domain)
        taxonomy_id = list(taxonomy_id)
        if len(taxonomy_id) > 0:
            text = utility.translate(
                taxonomy_id[0],
                context=self.real_context,
                target_language=lang)
            return text
        else:
            return None

    def get_relation_field(self, field_name):
        related_obj = self.get_value(field_name)
        if not related_obj:
            return None
        return related_obj.to_object

    def get_relation_value(self, field_name, value_name):
        if isinstance(value_name, list):
            result = []
            for value in value_name:
                relation_field = self.get_relation_field(field_name)
                result.append(getattr(relation_field, value, ''))
            return ' '.join(result)
        relation_field = self.get_relation_field(field_name)
        return getattr(relation_field, value_name, '')

    def get_info(self):
        obj = self.get_relation_field('contact')
        info = []
        phone = getattr(obj, 'phone', None)
        if not phone:
            obj = self.get_relation_field('organizer')
            phone = getattr(obj, 'phone', None)
        if phone:
            info.append(phone)
        website = getattr(obj, 'website', None)
        if website:
            info.append(website)
        return ' - '.join(info)


class TupleErrorPage(BrowserView):
    def __call__(self):
        event_col = self.context
        queries = []
        for query in event_col.query:
            if not isinstance(query.get('v'), tuple):
                queries.append(query)
        event_col.query = queries
        return 'End of tuple error'


class TransmoExport(BrowserView):
    def __call__(self):
        objects = {}
        # get all file in custom folder
        portal_skins = api.portal.get_tool('portal_skins')
        objects['custom'] = []
        for obj_id, item in portal_skins.custom.items():
            objects['custom'].append({
                'obj_id': obj_id,
                'meta_type': item.meta_type,
                'raw': item.raw
            })
        # get list of installed profile
        portal_quickinstaller = api.portal.get_tool('portal_quickinstaller')
        product_ids = [product['id'] for product in portal_quickinstaller.listInstalledProducts()]
        objects['products'] = product_ids
        return json.dumps(objects)
