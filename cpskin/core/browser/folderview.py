# -*- coding: utf-8 -*-
from Acquisition import aq_inner
from Acquisition import aq_parent
from cpskin.core.interfaces import IFolderViewSelectedContent
from cpskin.core.interfaces import IFolderViewWithBigImages
from cpskin.core.utils import image_scale
from cpskin.locales import CPSkinMessageFactory as _
from DateTime import DateTime
from datetime import datetime
from plone import api
from plone.app.contenttypes.browser.folder import FolderView as FoldV
from plone.app.contenttypes.content import Event
from plone.app.event.base import filter_and_resort
from plone.app.event.recurrence import RecurrenceSupport
from plone.app.querystring import queryparser
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.interfaces import IDexterityFTI
from plone.event.interfaces import IEvent
from Products.CMFCore.interfaces import IFolderish
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.i18nl10n import monthname_msgid
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.i18n import translate
from zope.interface import alsoProvides
from zope.interface import noLongerProvides
from zope.schema import getFields
from zope.schema.interfaces import IVocabularyFactory

import httpagentparser


ADDABLE_TYPES = ['Collection', 'Document', 'Folder']


class FolderView(FoldV):

    def _redirect(self, msg=''):
        if self.request:
            if msg:
                api.portal.show_message(message=msg,
                                        request=self.request,
                                        type='info')
            self.request.response.redirect(self.context.absolute_url())
        return msg

    def _get_real_context(self):
        context = self.context
        plone_view = getMultiAdapter((context, self.request), name='plone')
        if plone_view.isDefaultPageInFolder():
            context = aq_parent(context)
        context = aq_inner(context)
        return context

    def isFolderViewActivated(self, context=None):
        """Check if folderview is activated on context"""
        if context is None:
            context = self.context
        layout = context.getLayout()
        if layout == 'folderview':
            return True
        return False

    def can_configure(self):
        """Check if folderview can be configured on context"""
        context = self.context
        if not IFolderish.providedBy(context):
            return False
        already_activated = self.isFolderViewActivated()
        return (not already_activated)

    def configure(self):
        """Configure folders and collections for folderview"""
        context = self.context
        configure_folderviews(context)
        api.portal.show_message(
            message=_(u'Vue index avec collections configurée.'),
            request=self.request,
            type='info')
        self.request.response.redirect(context.absolute_url())
        return ''

    def is_event_collection(self, brains):
        if len(brains) > 0:
            obj = brains[0].getObject()
            return IEvent.providedBy(obj)
        return False

    def getResults(self, content):
        """Content is a Collection"""
        # Make a copy of the query to avoid modifying it
        query = list(content.query)
        index_view_keywords = getattr(content, 'index_view_keywords', False)
        # set query for homepage
        if index_view_keywords:
            homepage_keywords = content.index_view_keywords
            query.append({
                'i': 'hiddenTags',
                'o': 'plone.app.querystring.operation.selection.is',
                'v': homepage_keywords
            })
        sort_on = getattr(content, 'sort_on', None)
        sort_order = 'reverse' if getattr(content, 'sort_reversed', False) else 'ascending'  # noqa
        sort_reversed = getattr(content, 'sort_reversed', False)
        parsedquery = queryparser.parseFormquery(
            content,
            query,
            sort_on,
            sort_order
        )
        portal_catalog = api.portal.get_tool('portal_catalog')
        brains = portal_catalog(parsedquery)
        item_count_homepage = getattr(content, 'item_count_homepage', 8)
        if self.is_event_collection(brains):
            start = DateTime()
            sort_on = getattr(content, 'sort_on', 'start')
            if sort_on in ('start', 'end'):
                # set item_count to higher value to sort with all events
                item_count = getattr(content, 'item_count', 8)
                # item_count = content.item_count
                content.item_count = 1000
                filter_and_resort_brains = filter_and_resort(
                    content,
                    brains,
                    start,
                    None,
                    sort_on,
                    sort_reversed
                )
                brains = filter_and_resort_brains[:item_count_homepage]
                content.item_count = item_count
        else:
            brains = brains[:item_count_homepage]
        portal_catalog = api.portal.get_tool(name='portal_catalog')
        results = {'sticky-results': [],
                   'standard-results': []}
        for brain in brains:
            if portal_catalog.getIndexDataForRID(brain.getRID())['is_sticky']:
                results['sticky-results'].append(brain)
            else:
                results['standard-results'].append(brain)
        if not results['sticky-results'] and not results['standard-results']:
            return None
        return results

    def getContents(self):
        brains = self.searchSelectedContent()
        objects = [brain.getObject() for brain in brains]
        realObjects = []
        for obj in objects:
            if obj.portal_type == 'Folder':
                if obj.getDefaultPage() is not None:
                    realObject = getattr(obj, obj.getDefaultPage())
                    # check if realObject is a collection :
                    if getattr(realObject, 'results', None):
                        if len(realObject.results()) > 0:
                            realObjects.append(realObject)
                else:
                    continue
            else:
                realObjects.append(obj)
        return realObjects

    def isBigImage(self, number, results, resultType):
        """
        Check if image should be big depending on position and result type
        (sticky / non-sticky)
        """
        if not self.bigImagesAreUsed():
            return False
        if resultType == 'sticky-results' and number < 5:
            return True
        elif resultType == 'standard-results' and \
                number < 5 - len(results['sticky-results']):
            return True
        return False

    def getThumbSize(self, obj, isBigImage=False):
        prefix = 'image'
        thumbSize = 'thumb'
        if getattr(obj, 'hasContentLeadImage', None):
            prefix = 'leadImage'
        if isBigImage:
            thumbSize = 'mini'
        return '%s_%s' % (prefix, thumbSize)

    def searchSelectedContent(self):
        path = '/'.join(self.context.getPhysicalPath())
        portal_catalog = api.portal.get_tool('portal_catalog')
        queryDict = {}
        queryDict['path'] = {'query': path, 'depth': 1}
        queryDict['portal_type'] = ADDABLE_TYPES
        queryDict['object_provides'] = IFolderViewSelectedContent.__identifier__  # noqa
        queryDict['sort_on'] = 'getObjPositionInParent'
        queryDict['review_state'] = (
            'published_and_hidden',
            'published_and_shown',
            'published'
        )
        results = portal_catalog.searchResults(queryDict)
        return results

    def getSliderType(self):
        portal_registry = getToolByName(self.context, 'portal_registry')
        return portal_registry['cpskin.core.interfaces.ICPSkinSettings.slider_type']  # noqa

    def hasFlexSlider(self):
        """Check if flexslider is available and installed"""
        try:
            from cpskin.slider.interfaces import ICPSkinSliderLayer
        except ImportError:
            return False
        else:
            request = getattr(self.context, 'REQUEST', None)
            if ICPSkinSliderLayer.providedBy(request):
                return True
            return False

    def is_browser_compatible(self):
        results = True
        request = getattr(self.context, 'REQUEST', None)
        http_user_agent = request.getHeader('HTTP_USER_AGENT')
        browser_user_agent = httpagentparser.detect(http_user_agent)
        if browser_user_agent:
            browser = browser_user_agent.get('browser')
            if browser:
                if 'Internet Explorer' in browser.get('name'):
                    results = int(browser['version'].split('.')[0]) >= 9
        return results

    def addContent(self):
        """Mark content to add it to folder view"""
        context = self._get_real_context()
        alsoProvides(context, IFolderViewSelectedContent)
        catalog = api.portal.get_tool('portal_catalog')
        catalog.reindexObject(context)
        self._redirect(_(u'Contenu ajouté à la vue index.'))

    def removeContent(self):
        """Unmark content to remove it from folder view"""
        context = self._get_real_context()
        noLongerProvides(context, IFolderViewSelectedContent)
        catalog = api.portal.get_tool('portal_catalog')
        catalog.reindexObject(context)
        self._redirect(_(u'Contenu retiré de la vue index.'))

    def isEligibleContent(self):
        context = self._get_real_context()
        if context.portal_type not in ADDABLE_TYPES:
            return False
        parent = aq_parent(context)
        if not self.isFolderViewActivated(parent):
            return False
        return True

    def canAddContent(self):
        if not self.isEligibleContent():
            return False
        context = self._get_real_context()
        if IFolderViewSelectedContent.providedBy(context):
            return False
        return True

    def canRemoveContent(self):
        if not self.isEligibleContent():
            return False
        context = self._get_real_context()
        if not IFolderViewSelectedContent.providedBy(context):
            return False
        return True

    def canUseBigImages(self):
        """Check if big images can be used on folder view"""
        if not self.isFolderViewActivated():
            return False
        context = self._get_real_context()
        return (not IFolderViewWithBigImages.providedBy(context))

    def bigImagesAreUsed(self):
        context = self._get_real_context()
        return IFolderViewWithBigImages.providedBy(context)

    def canStopBigImagesUse(self):
        """Check if big images are used on folder view"""
        if not self.isFolderViewActivated():
            return False
        return (self.bigImagesAreUsed())

    def useBigImages(self):
        """Use big images for first elements on folder view"""
        context = self._get_real_context()
        alsoProvides(context, IFolderViewWithBigImages)
        catalog = api.portal.get_tool('portal_catalog')
        catalog.reindexObject(context)
        self._redirect(_(u'Big images are now used on this folder view.'))

    def stopBigImagesUse(self):
        """Use using big images for first elements on folder view"""
        context = self._get_real_context()
        noLongerProvides(context, IFolderViewWithBigImages)
        catalog = api.portal.get_tool('portal_catalog')
        catalog.reindexObject(context)
        self._redirect(
            _(u'Big images are not used anymore on this folder view.'))

    def slider_config(self, content_id):
        portal_registry = getToolByName(self.context, 'portal_registry')
        slider_timer = portal_registry[
            'cpskin.core.interfaces.ICPSkinSettings.slider_timer']
        auto_play_slider = portal_registry[
            'cpskin.core.interfaces.ICPSkinSettings.auto_play_slider']
        config = """
        (function($) {
            "use strict";
            var animation = "slide";
            // IE 9 does not support 'slide' animation
            if (navigator.sayswho === 'MSIE 9' || navigator.sayswho === 'IE 9')
            {
            animation = "fade";
            }
            $('#carousel-%(content_id)s').flexslider({
              animation: animation,
              controlNav: false,
              animationLoop: false,
              slideshow: false,
              itemWidth: 210,
              itemMargin: 5,
              asNavFor: '#slider-%(content_id)s',
            });
            $('#slider-%(content_id)s').flexslider({
              animation: animation,
              controlNav: false,
              animationLoop: true,
              slideshow: %(auto_play_slider)s,
              slideshowSpeed: %(slider_timer)s,
              sync: "#carousel-%(content_id)s"
            });
         })(jQuery);
        """ % {'auto_play_slider': auto_play_slider and 'true' or 'false',
               'slider_timer': slider_timer,
               'content_id': content_id}
        return config

    def is_dexterity(self):
        portal_types = api.portal.get_tool('portal_types')
        if portal_types.get('Image').meta_type == 'Dexterity FTI':
            return True
        else:
            return False

    def scaled_image_url(self, context, obj, isBigImage):
        if self.is_dexterity():
            image = self.collection_image_scale(context, obj)
            return image and image.url or ''
        else:
            thumbsize = self.getThumbSize(obj, isBigImage)
            url = '{0}/{1}'.format(obj.absolute_url(), thumbsize)
            return url

    def collection_image_scale(self, collection, obj):
        scale = getattr(collection, 'collection_image_scale', 'mini')
        if self.use_new_template(collection):
            return image_scale(obj, 'newsImage', scale, generate_tag=False)
        else:
            return image_scale(obj, 'newsImage', scale)

    def see_all(self, collection):
        voirlensemble = _(u"Voir l'ensemble des")
        coll_lang = getattr(collection, 'language')
        lang = coll_lang if (coll_lang != '' and '-' not in coll_lang) else 'fr'  # noqa
        trans = translate(
            voirlensemble,
            domain=voirlensemble.domain,
            target_language=lang)
        if getattr(collection, 'link_text', ''):
            return collection.link_text.encode('utf-8')
        return '{0} {1}'.format(trans, collection.Title().lower())

    def see_categories(self, collection):
        result = True
        taxonomy_field = getattr(collection, 'taxonomy_category', '')
        if not taxonomy_field:
            result = False
        return result

    def get_categories(self, collection, obj):
        portal_type = obj.portal_type
        schema = getUtility(IDexterityFTI, name=portal_type).lookupSchema()
        fields = getFields(schema)
        taxonomy_field = getattr(collection, 'taxonomy_category', '')
        if taxonomy_field not in fields.keys():
            return ''

        field = fields[taxonomy_field]
        vocabulary_name = field.value_type.vocabularyName
        factory = getUtility(IVocabularyFactory, vocabulary_name)
        vocabulary = factory(api.portal.get())
        tokens = getattr(obj, taxonomy_field, '')
        if not tokens:
            return ''
        categories = []
        for token in tokens:
            cat = vocabulary.inv_data.get(token)
            categories.append(cat[1:])
        categories.sort()
        return ', '.join(categories)

    def toLocalizedTime(self,
                        time=None,
                        long_format=None,
                        time_only=None,
                        event=None,
                        startend='start'):
        if event:
            if not isinstance(event, Event):
                event = event.getObject()
            if IDexterityContent.providedBy(event):
                rs = RecurrenceSupport(event)
                occurences = [occ for occ in rs.occurrences(datetime.today())]
                if len(occurences) >= 1:
                    # do not get object which started in the past
                    time = getattr(occurences[0], startend)
        return self.context.restrictedTraverse('@@plone').toLocalizedTime(
            time, long_format, time_only)

    def to_day(self, result):
        date = getattr(result, 'start')
        if not date:
            return ''
        day = date.day()
        return str(day)

    def to_localized_month(self, result):
        date = getattr(result, 'start')
        if not date:
            return ''
        month = translate(
            monthname_msgid(date.month()),
            'plonelocales',
            context=self.request
        )
        return month

    def is_one_day(self, event):
        if not IDexterityContent.providedBy(event):
            return self.toLocalizedTime(event.start_date, long_format=0) == self.toLocalizedTime(event.end_date, long_format=0)  # noqa
        return self.toLocalizedTime(event.start, long_format=0) == self.toLocalizedTime(event.end, long_format=0)  # noqa

    def is_with_hours(self, event):
        if not IDexterityContent.providedBy(event):
            return self.toLocalizedTime(event.start_date, long_format=1)[11:] != '00:00' or self.toLocalizedTime(event.end_date, long_format=1)[11:] != '00:00'  # noqa
        if getattr(event, 'whole_day', False):
            return not(event.whole_day)
        else:
            return self.toLocalizedTime(event.start, long_format=1)[11:] != '00:00' or self.toLocalizedTime(event.end, long_format=1)[11:] != '00:00'  # noqa

    def is_open_end(self, event):
        if not IDexterityContent.providedBy(event):
            return False
        else:
            return getattr(event, 'open_end', False)

    def see_start_end_date(self, brain, collection):
        if getattr(brain, 'start', False) and getattr(brain, 'end', False):
            if not getattr(collection, 'hide_date', False):
                return True
            else:
                return False
        else:
            return False

    def hide_title(self, collection):
        return getattr(collection, 'hide_title', False)

    def hide_see_all_link(self, collection):
        return getattr(collection, 'hide_see_all_link', False)

    def hide_date(self, brain, collection):
        """Check if object has a correct effective date.
        If None, you get 01/01/1000 and strftime cannot convert it.
        Also check if collection is checked to see publication date.
        """
        if not getattr(brain, 'start', None) and not getattr(brain, 'end', None):  # noqa
            return getattr(collection, 'hide_date', True)
        else:
            # always hide effective date for events
            return True

    def show_day_and_month(self, collection):
        return getattr(collection, 'show_day_and_month', False)

    def show_descriptions(self, collection):
        return getattr(collection, 'show_descriptions', False)

    def use_new_template(self, collection):
        return getattr(collection, 'use_new_template', False)


def configure_folderviews(context):
    """
    """
    existingIds = context.objectIds()
    portalPath = api.portal.get().getPhysicalPath()
    contextPath = '/'.join(context.getPhysicalPath()[len(portalPath):])
    if 'a-la-une' not in existingIds:
        folder = api.content.create(container=context,
                                    type='Folder',
                                    id='a-la-une',
                                    title=_(u'À la une'))
        alsoProvides(folder, IFolderViewSelectedContent)
        collection = api.content.create(container=folder,
                                        type='Collection',
                                        id='a-la-une',
                                        title=_(u'À la une'))
        query = [{'i': 'hiddenTags',
                  'o': 'plone.app.querystring.operation.selection.is',
                  'v': 'a-la-une'},
                 {'i': 'path',
                  'o': 'plone.app.querystring.operation.string.path',
                  'v': '/%s' % contextPath}]
        collection.setQuery(query)
        collection.setSort_on('effective')
        collection.setSort_reversed(True)
        collection.setLayout('summary_view')
        folder.setDefaultPage('a-la-une')
        folder.reindexObject()
    if 'actualites' not in existingIds:
        folder = api.content.create(container=context,
                                    type='Folder',
                                    id='actualites',
                                    title=_(u'Actualités'))
        collection = api.content.create(container=folder,
                                        type='Collection',
                                        id='actualites',
                                        title=_(u'Actualités'))
        query = [{'i': 'portal_type',
                  'o': 'plone.app.querystring.operation.selection.is',
                  'v': ['News Item']},
                 {'i': 'path',
                  'o': 'plone.app.querystring.operation.string.path',
                  'v': '/%s' % contextPath}]
        collection.setQuery(query)
        collection.setSort_on('effective')
        collection.setSort_reversed(True)
        collection.setLayout('summary_view')
        folder.setDefaultPage('actualites')
    else:
        folder = context['actualites']
    alsoProvides(folder, IFolderViewSelectedContent)
    folder.reindexObject()

    if 'evenements' not in existingIds:
        folder = api.content.create(container=context,
                                    type='Folder',
                                    id='evenements',
                                    title=_(u'Événements'))
        collection = api.content.create(container=folder,
                                        type='Collection',
                                        id='evenements',
                                        title=_(u'Événements'))
        query = [{'i': 'portal_type',
                  'o': 'plone.app.querystring.operation.selection.is',
                  'v': ['Event']},
                 {'i': 'path',
                  'o': 'plone.app.querystring.operation.string.path',
                  'v': '/%s' % contextPath}]
        collection.setQuery(query)
        collection.setSort_on('effective')
        collection.setSort_reversed(True)
        collection.setLayout('summary_view')
        folder.setDefaultPage('evenements')
    else:
        folder = context['evenements']
    alsoProvides(folder, IFolderViewSelectedContent)
    folder.reindexObject()
    context.setLayout('folderview')
