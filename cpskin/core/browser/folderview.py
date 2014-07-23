# -*- coding: utf-8 -*-

from Acquisition import aq_parent
from zope.interface import alsoProvides
from zope.interface import noLongerProvides
from plone import api
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import IFolderish

from cpskin.core.interfaces import IFolderViewSelectedContent

from cpskin.locales import CPSkinMessageFactory as _

ADDABLE_TYPES = ['Collection', 'Document']


class FolderView(BrowserView):

    def _redirect(self, msg=''):
        if self.request:
            if msg:
                api.portal.show_message(message=msg,
                                        request=self.request,
                                        type='info')
            self.request.response.redirect(self.context.absolute_url())
        return msg

    def isFolderViewActivated(self, context=None):
        """
        Check if folderview is activated on context
        """
        if context is None:
            context = self.context
        layout = context.getLayout()
        if layout == 'folderview':
            return True
        return False

    def can_configure(self):
        """
        Check if folderview can be configured on context
        """
        context = self.context
        if not IFolderish.providedBy(context):
            return False
        alreadyActivated = self.isFolderViewActivated()
        return (not alreadyActivated)

    def configure(self):
        """
        Configure folders and collections for folderview
        """
        context = self.context
        existingIds = context.objectIds()
        portalPath = api.portal.get().getPhysicalPath()
        contextPath = '/'.join(context.getPhysicalPath()[len(portalPath):])
        if 'a-la-une' not in existingIds:
            folder = api.content.create(container=context,
                                        type='Folder',
                                        id='a-la-une',
                                        title="À la une")
            collection = api.content.create(container=folder,
                                            type='Collection',
                                            id='a-la-une',
                                            title="À la une")
            query = [{'i': 'hiddenTags',
                      'o': 'plone.app.querystring.operation.selection.is',
                      'v': 'a-la-une'},
                      {'i': 'path',
                      'o': 'plone.app.querystring.operation.string.path',
                      'v': '/%s' % contextPath}]
            collection.setQuery(query)
            collection.setSort_on('effective')
            collection.setSort_reversed(True)
            collection.setLayout('folder_summary_view')
            alsoProvides(collection, IFolderViewSelectedContent)
            folder.setDefaultPage('a-la-une')
        if 'actualites' not in existingIds:
            folder = api.content.create(container=context,
                                        type='Folder',
                                        id='actualites',
                                        title="Actualités")
            collection = api.content.create(container=folder,
                                            type='Collection',
                                            id='actualites',
                                            title="Actualités")
            query = [{'i': 'portal_type',
                      'o': 'plone.app.querystring.operation.selection.is',
                      'v': ['News Item']},
                      {'i': 'path',
                      'o': 'plone.app.querystring.operation.string.path',
                      'v': '/%s' % contextPath}]
            collection.setQuery(query)
            collection.setSort_on('effective')
            collection.setSort_reversed(True)
            collection.setLayout('folder_summary_view')
            alsoProvides(collection, IFolderViewSelectedContent)
            folder.setDefaultPage('actualites')
        if 'evenements' not in existingIds:
            folder = api.content.create(container=context,
                                        type='Folder',
                                        id='evenements',
                                        title="Événements")
            collection = api.content.create(container=folder,
                                            type='Collection',
                                            id='evenements',
                                            title="Événements")
            query = [{'i': 'portal_type',
                      'o': 'plone.app.querystring.operation.selection.is',
                      'v': ['Event']},
                      {'i': 'path',
                      'o': 'plone.app.querystring.operation.string.path',
                      'v': '/%s' % contextPath}]
            collection.setQuery(query)
            collection.setSort_on('effective')
            collection.setSort_reversed(True)
            collection.setLayout('folder_summary_view')
            alsoProvides(collection, IFolderViewSelectedContent)
            folder.setDefaultPage('evenements')

        context.setLayout('folderview')
        api.portal.show_message(message=_(u"Vue index avec collections configurée."),
                                request=self.request,
                                type='info')
        self.request.response.redirect(context.absolute_url())
        return ''

    def getContents(self):
        brains = self.searchSelectedContent()
        return [brain.getObject() for brain in brains]

    def searchSelectedContent(self):
        path = '/'.join(self.context.getPhysicalPath())
        portal_catalog = getToolByName(self.context, 'portal_catalog')
        queryDict = {}
        queryDict['path'] = {'query': path, 'depth': 2}
        queryDict['portal_type'] = ['Document', 'Collection']
        queryDict['object_provides'] = IFolderViewSelectedContent.__identifier__
        queryDict['sort_on'] = 'getObjPositionInParent'
        results = portal_catalog.searchResults(queryDict)
        return results

    def hasFlexSlider(self):
        """
        Check if flexslider is available and installed
        """
        try:
            from cpskin.slider.interfaces import ICPSkinSliderLayer
        except ImportError:
            return False
        else:
            request = getattr(self.context, "REQUEST", None)
            if ICPSkinSliderLayer.providedBy(request):
                return True
            return False

    def addContent(self):
        """
        Mark content to add it to folder view
        """
        context = self.context
        alsoProvides(context, IFolderViewSelectedContent)
        catalog = api.portal.get_tool('portal_catalog')
        catalog.reindexObject(context)
        self._redirect(_(u'Contenu ajouté à la vue index.'))

    def removeContent(self):
        """
        Unmark content to remove it from folder view
        """
        context = self.context
        noLongerProvides(context, IFolderViewSelectedContent)
        catalog = api.portal.get_tool('portal_catalog')
        catalog.reindexObject(context)
        self._redirect(_(u'Contenu retiré de la vue index.'))

    def isEligibleContent(self):
        if self.context.portal_type not in ADDABLE_TYPES:
            return False
        parent = aq_parent(self.context)
        if not self.isFolderViewActivated(parent) \
           and not self.isFolderViewActivated(aq_parent(parent)):
            return False
        return True

    def canAddContent(self):
        if not self.isEligibleContent():
            return False
        if IFolderViewSelectedContent.providedBy(self.context):
            return False
        return True

    def canRemoveContent(self):
        if not self.isEligibleContent():
            return False
        if not IFolderViewSelectedContent.providedBy(self.context):
            return False
        return True
