# -*- coding: utf-8 -*-
import random

from Acquisition import aq_inner
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone import api
from plone.app.layout.navigation.interfaces import INavigationRoot
from plone.app.layout.viewlets.common import ViewletBase
from zope.component import getMultiAdapter

from cpskin.core.utils import has_crop


HAS_MINISITE = False
try:
    from cpskin.minisite.interfaces import IInMinisite
    from cpskin.minisite.interfaces import IInPortal
    HAS_MINISITE = True
except ImportError:
    pass


class CPSkinBannerViewlet(ViewletBase):
    render = ViewPageTemplateFile('banner.pt')

    def available(self):
        context = self.context
        banner_view = getMultiAdapter((context, self.request),
                                      name="banner_activation")
        return banner_view.is_enabled

    def isInMinisite(self):
        if not HAS_MINISITE:
            return False
        return (self.isInMinisiteMode() or self.isInPortalMode())

    def show_slogan(self):
        portal_registry = api.portal.get_tool('portal_registry')
        show_slogan = portal_registry[
            'cpskin.core.interfaces.ICPSkinSettings.show_slogan']
        return show_slogan

    def get_slogan(self):
        default = {
            'title': '',
            'description': '',
        }
        if not self.isFolderView():
            return default
        banner = self.getBanner()
        if not banner['object']:
            return default
        obj = banner['object']
        return {
            'title': obj.Title(),
            'description': obj.Description(),
        }

    def homeUrl(self):
        """
        Returns URL of :
         - object where banner was activated if not in a minisite
         - minisite root object if in a minisite
        """
        context = self.context
        request = self.request
        if not HAS_MINISITE or not self.isInMinisite():
            banner_view = getMultiAdapter((context, request),
                                          name="banner_activation")
            return banner_view.banner_root.absolute_url()
        else:
            portal = api.portal.get()
            minisite = request.get('cpskin_minisite', None)
            minisiteRoot = portal.unrestrictedTraverse(minisite.search_path)
            return minisiteRoot.absolute_url()

    def isHomepage(self):
        if self.isInMinisite():
            return False
        obj = aq_inner(self.context)
        return INavigationRoot.providedBy(obj)

    def isFolderView(self):
        context = self.context
        layout = context.getLayout()
        return (layout == 'folderview')

    def isInMinisiteMode(self):
        if not HAS_MINISITE:
            return False
        request = self.request
        return IInMinisite.providedBy(request)

    def isInPortalMode(self):
        if not HAS_MINISITE:
            return False
        request = self.request
        return IInPortal.providedBy(request)

    def getUnscaleUrl(self, obj, fieldname, scale):
        if 'obj' is None:
            return ''
        if fieldname in ('video'):
            print (fieldname + 'Sous-chaîne trouvée')
            banner_url = obj.absolute_url()
            return banner_url
        if has_crop(obj, fieldname, scale):
            view = obj.restrictedTraverse('@@images')
            scale = view.scale(fieldname, scale=scale)
            banner_url = scale.absolute_url()
        else:
            banner_url = '{0}/@@images/{1}'.format(
                obj.absolute_url(),
                fieldname,
            )
        return banner_url

    def getBanner(self):
        context = self.context
        local_banner_folder = getattr(context.aq_explicit, 'banner', None)
        local_banner_event = getattr(context.aq_explicit, 'image_banner', None)
        local_banner = getattr(context.aq_explicit, 'banner.jpg', None)
        banner_folder = getattr(context, 'banner', None)
        banner = getattr(context, 'banner.jpg', None)
        banner_video_folder = getattr(context, 'banner-video', None)
        if context.portal_type == 'Event' and local_banner_event:
            return {
                'object': context,
                'url': self.getUnscaleUrl(context, 'image_banner', 'banner'),
            }
        if banner_video_folder and (not local_banner and not local_banner_folder ): 
            banner_folder_to_use = banner_video_folder
            brains = api.content.find(
                context=banner_folder_to_use,
                portal_type='File',
            )
            if brains:
                brain = brains[random.randrange(len(brains))]
                obj = brain.getObject()
                return {
                    'object': obj,
                    'url': self.getUnscaleUrl(obj, 'video', 'banner'),
                }
        if local_banner_folder or (banner_folder and not local_banner):
            banner_folder_to_use = local_banner_folder and local_banner_folder or banner_folder
            brains = api.content.find(
                context=banner_folder_to_use,
                portal_type='Image',
            )
            if brains:
                brain = brains[random.randrange(len(brains))]
                obj = brain.getObject()
                return {
                    'object': obj,
                    'url': self.getUnscaleUrl(obj, 'image', 'banner'),
                }
        return {
            'object': banner,
            'url': self.getUnscaleUrl(banner, 'image', 'banner'),
        }

    def getImageBannerUrl(self):
        banner = self.getBanner()
        return banner['url']
