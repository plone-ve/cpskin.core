# -*- coding: utf-8 -*-
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName


class FolderView(BrowserView):

    def getNews(self, navigation_root_path):
        path = '/'.join([navigation_root_path, 'actualites'])
        return self.searchCollection(path)

    def getEvents(self, navigation_root_path):
        path = '/'.join([navigation_root_path, 'evenements'])
        return self.searchCollection(path)

    def searchCollection(self, path):
        portal_catalog = getToolByName(self.context, 'portal_catalog')
        queryDict = {}
        queryDict['path'] = {'query': path, 'depth': 1}
        queryDict['portal_type'] = 'Collection'
        queryDict['sort_limit'] = 1
        collections = portal_catalog.searchResults(queryDict)
        return collections and collections[0] or None

    def getFrontPageText(self):
        frontPage = getattr(self.context, 'front-page', None)
        if frontPage is None:
            return
        if frontPage.Language() == self.context.Language():
            return frontPage.getText()
        if hasattr(frontPage, 'getTranslation'):
            lang = self.context.REQUEST.get('LANGUAGE', 'fr')
            frontPage = frontPage.getTranslation(lang)
        return frontPage.getText()

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

    def getSliderContent(self):
        container = getattr(self.context, 'a-la-une', None)
        if container is None:
            return []
        return container.queryCatalog()