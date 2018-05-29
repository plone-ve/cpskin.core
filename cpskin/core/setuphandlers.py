# -*- coding: utf-8 -*-
from cpskin.core.behaviors.directory import ICpskinDirectoryViewSettings
from cpskin.core.behaviors.eventview import ICpskinEventViewSettings
from cpskin.core.behaviors.indexview import ICpskinIndexViewSettings
from cpskin.core.behaviors.organization import IOrganizationImages
from cpskin.core.utils import add_behavior
from cpskin.core.utils import set_exclude_from_nav
from cpskin.locales import CPSkinMessageFactory as _
from plone import api
from plone.app.viewletmanager.interfaces import IViewletSettingsStorage
from plone.app.viewletmanager.manager import ManageViewlets
from plone.registry import field
from plone.registry import Record
from plone.registry.interfaces import IRegistry
from Products.CMFDefault.utils import bodyfinder
from zope.component import getUtility
from zope.component import queryMultiAdapter
from zope.interface import noLongerProvides

import logging
import os


logger = logging.getLogger('cpskin.core')


def installCore(context):
    if context.readDataFile('cpskin.core-default.txt') is None:
        return

    logger.info('Installing')
    portal = api.portal.get()

    # Rename events and news
    ChangeCollectionsIds(portal)

    # Add the MaildropHost if possible
    addMaildropHost(portal)

    # Add catalog indexes
    addCatalogIndexes(portal)

    # Create default banner image
    addImageFromFile(portal, 'banner.jpg')

    # Create default visuel image
    addImageFromFile(portal, 'visuel.png')

    # Create default logo
    addImageFromFile(portal, 'cpskinlogo.png')

    add_behavior('Collection', ICpskinIndexViewSettings.__identifier__)
    add_behavior('Event', ICpskinEventViewSettings.__identifier__)
    add_behavior('organization', IOrganizationImages.__identifier__)
    add_behavior('directory', ICpskinDirectoryViewSettings.__identifier__)

    # Create footer static page
    footer_name = 'footer-static'
    if not portal.hasObject(footer_name):
        footer = api.content.create(type='Document',
                                    title=footer_name,
                                    container=portal)
        footer.setTitle(footer_name)

    configCollectiveQucikupload(portal)

    addLoadPageMenuToRegistry()
    addAutoPlaySliderToRegistry()
    addSliderTimerToRegistry()
    addCityNameToRegistry()
    addSubMenuPersistenceToRegistry()
    addSliderTypeToRegistry()
    set_googleapi_key()
    upgrade_front_page()
    order_portaltop_viewlets()
    add_other_xhtml_valid_tags()


def add_other_xhtml_valid_tags():
    portal_transforms = api.portal.get_tool('portal_transforms')
    safe_html = getattr(portal_transforms, 'safe_html')
    key = 'valid_tags'
    valids = safe_html.get_parameter_value('valid_tags')
    other_tags = ['figcaption']
    kwargs = {}
    kwargs[key + '_key'] = valids.keys()
    kwargs[key + '_value'] = [str(s) for s in valids.values()]
    for tag in other_tags:
        if tag not in valids.keys():
            kwargs[key + '_key'].append(tag)
            kwargs[key + '_value'].append('1')
            logger.info('Add {0} to valid html tags'.format(tag))
    safe_html.set_parameters(**kwargs)
    safe_html._p_changed = True
    safe_html.reload()


def order_portaltop_viewlets():
    storage = getUtility(IViewletSettingsStorage)
    manager_name = 'plone.portaltop'
    portal = api.portal.get()
    skinname = portal.getCurrentSkinName()
    view = ManageViewlets(portal, portal.REQUEST)
    order = view._getOrder(manager_name)
    order.insert(1, 'cpskin.banner')
    storage.setOrder(manager_name, skinname, order)


def uninstallCore(context):
    if context.readDataFile('cpskin.core-uninstall.txt') is None:
        return

    logger.info('Uninstalling')
    portal = api.portal.get()

    # Remove banner image
    if portal.hasObject('banner.jpg'):
        api.content.delete(obj=portal['banner.jpg'])

    # Remove visuel image
    if portal.hasObject('visuel.png'):
        api.content.delete(obj=portal['visuel.png'])

    # Remove default logo
    if portal.hasObject('cpskinlogo.png'):
        api.content.delete(obj=portal['cpskinlogo.png'])

    # Remove footer static
    if portal.hasObject('footer-static'):
        api.content.delete(obj=portal['footer-static'])

    unregisterProvidesInterfaces(portal)


def unregisterProvidesInterfaces(portal):
    from cpskin.core.interfaces import (
        IBannerActivated,
        IMediaActivated,
        IAlbumCollection,
        IVideoCollection
    )

    interfaces = [IBannerActivated,
                  IMediaActivated,
                  IAlbumCollection,
                  IVideoCollection]
    for interface in interfaces:
        catalog = api.portal.get_tool('portal_catalog')
        brains = catalog({
            'object_provides': interface.__identifier__,
        })
        for brain in brains:
            obj = brain.getObject()
            noLongerProvides(obj, interface)
            obj.reindexObject()


def setPageText(portal, page, viewName):
    """
    Sets text of a Plone document if it exists and reindex the document
    The text is coming from a browser view template <body> tag
    """
    if page is None:
        return
    request = getattr(portal, 'REQUEST', None)
    if request is not None:
        view = queryMultiAdapter((portal, request), name=viewName)
        if view is not None:
            text = bodyfinder(view.index()).strip()
            try:
                page.setText(text, mimetype='text/html')
            except:
                from plone.app.textfield.value import RichTextValue
                rtv = RichTextValue(text)
                page.text = rtv
            page.reindexObject()


def addMaildropHost(self):
    """
     Add a MaildropHost if Products.MaildropHost is available...
     If MaildropHost exist, PloneGazette will use it to send mails.
     This will avoid duplicate emails send as reported by
    """
    portal = api.portal.get_tool('portal_url').getPortalObject()
    if not getattr(portal, 'MaildropHost', None):
        try:
            portal.manage_addProduct['MaildropHost'].manage_addMaildropHost(
                'MaildropHost', title='MaildropHost')
        except AttributeError:
            # if MaildropHost is not available, we pass...
            pass


def addCatalogIndexes(portal):
    """
    Method to add our wanted indexes to the portal_catalog.
    We couldn't do it in the profile directly, see :
        http://maurits.vanrees.org/weblog/archive/2009/12/catalog
    """
    catalog = api.portal.get_tool('portal_catalog')
    indexes = catalog.indexes()
    wanted = (('standardTags', 'KeywordIndex'),
              ('iamTags', 'KeywordIndex'),
              ('isearchTags', 'KeywordIndex'),
              ('hiddenTags', 'KeywordIndex'))
    indexables = []
    for name, meta_type in wanted:
        if name not in indexes:
            catalog.addIndex(name, meta_type)
            indexables.append(name)
            logger.info('Added {0} for field {1}.'.format(meta_type, name))
    if len(indexables) > 0:
        logger.info('Indexing new indexes {0}.'.format(', '.join(indexables)))
        catalog.manage_reindexIndex(ids=indexables)


def ChangeCollectionsIds(portal):
    # required : topic object need a _p_jar for rename
    import transaction
    transaction.savepoint()
    if portal.hasObject('news'):
        news = portal['news']
        if news.hasObject('aggregator'):
            set_exclude_from_nav(news['aggregator'])
            api.content.rename(obj=news['aggregator'], new_id='index')
        set_exclude_from_nav(news)
        api.content.rename(obj=news, new_id='actualites')
    if portal.hasObject('events'):
        events = portal['events']
        if events.hasObject('aggregator'):
            set_exclude_from_nav(events['aggregator'])
            api.content.rename(obj=events['aggregator'], new_id='index')
        set_exclude_from_nav(events)
        api.content.rename(obj=events, new_id='evenements')


def addImageFromFile(portal, fileName):
    dataPath = os.path.join(os.path.dirname(__file__), 'data')
    filePath = os.path.join(dataPath, fileName)
    if not portal.hasObject(fileName):
        # with deterity image
        from plone.namedfile.file import NamedBlobImage
        namedblobimage = NamedBlobImage(
            data=open(filePath, 'r').read(),
            filename=unicode(fileName)
        )
        image = api.content.create(type='Image',
                                   title=fileName,
                                   image=namedblobimage,
                                   container=portal,
                                   language='fr')
        image.setTitle(fileName)
        image.reindexObject()


def configCollectiveQucikupload(portal):
    ptool = api.portal.get_tool('portal_properties')
    qu_props = ptool.get('quickupload_properties')
    if not qu_props.hasProperty('show_upload_action'):
        qu_props._setProperty('show_upload_action', True, 'boolean')
    else:
        qu_props.show_upload_action = True
    if not qu_props.hasProperty('sim_upload_limit'):
        qu_props._setProperty('sim_upload_limit', 1, 'int')
    else:
        qu_props.sim_upload_limit = 1


def addLoadPageMenuToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.load_page_menu' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.load_page_menu to registry')  # noqa
    record = Record(field.Bool(title=_(u'Load page menu'),
                               description=_(
                                   u'Is level 1 menu load page at click?'),
                               required=False,
                               default=False),
                    value=False)
    records['cpskin.core.interfaces.ICPSkinSettings.load_page_menu'] = record


def addSubMenuPersistenceToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.sub_menu_persistence' in records:  # noqa
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.sub_menu_persistence to registry')  # noqa
    record = Record(field.Bool(title=_(u'Sub menu persistence'),
                               description=_(u'Is level 2 menu persist?'),
                               required=False,
                               default=True),
                    value=True)
    records['cpskin.core.interfaces.ICPSkinSettings.sub_menu_persistence'] = record  # noqa


def addAutoPlaySliderToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.auto_play_slider' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.auto_play_slider to registry')  # noqa
    record = Record(
        field.Bool(
            title=_(u'Auto play slider'),
            description=_(u'Is the front page slider automatically play?'),
            required=False,
            default=True),
        value=True)
    records['cpskin.core.interfaces.ICPSkinSettings.auto_play_slider'] = record


def addSliderTimerToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.slider_timer' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.slider_timer to registry')  # noqa
    record = Record(
        field.Int(
            title=_(u'Slider timer'),
            description=_(u'Number of seconds between each transition.'),
            required=False,
            default=5000),
        value=5000)
    records['cpskin.core.interfaces.ICPSkinSettings.slider_timer'] = record


def addCityNameToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.city_name' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.city_name to registry')
    portal = api.portal.get()
    site_id = portal.getId()
    city_name = unicode(site_id.capitalize())
    record = Record(
        field.TextLine(
            title=_(u'City name'),
            description=_(u'City name variable used in some template.'),
            required=True,
            default=u'City name'),
        value=city_name)
    records['cpskin.core.interfaces.ICPSkinSettings.city_name'] = record


def addSliderTypeToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.slider_type' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.slider_type to registry')  # noqa
    record = Record(
        field.TextLine(
            title=_(u'Slider type'),
            description=_(u'Choose an horizontal or vertical slider.'),
            required=True,
            default=u'slider_view'),
        value=u'slider_view')
    records['cpskin.core.interfaces.ICPSkinSettings.slider_type'] = record


def addPortletsInRightActionsToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records

    if 'cpskin.core.interfaces.ICPSkinSettings.show_portlets_in_right_actions_panel' in records:  # noqa
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.show_portlets_in_right_actions_panel to registry')  # noqa
    record = Record(field.Bool(title=_(u'Show (right) portlets in right actions panel'),
                               description=_(u'Show (right) portlets (if any) in right actions panel after related contents.'),  # noqa
                               required=False,
                               default=False),
                    value=False)
    records['cpskin.core.interfaces.ICPSkinSettings.show_portlets_in_right_actions_panel'] = record  # noqa


def addTopMenuLeadImageToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records

    if 'cpskin.core.interfaces.ICPSkinSettings.show_leadimage_in_action_menu' in records:  # noqa
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.show_leadimage_in_action_menu to registry')  # noqa
    record = Record(field.Bool(title=_(u'Show leadimage in action menu'),
                               description=_(u'Show leadimage (if any) in the top action menu with content selected in the field before.'),  # noqa
                               required=False,
                               default=False),
                    value=False)
    records['cpskin.core.interfaces.ICPSkinSettings.show_leadimage_in_action_menu'] = record  # noqa


def addTopMenuContentsToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records
    if 'cpskin.core.interfaces.ICPSkinSettings.contents_in_action_menu' in records:  # noqa
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.contents_in_action_menu to registry')  # noqa
    record = Record(field.Tuple(title=_(u'Content to show in special action menu (top)'),
                                description=_(u'Please select which contents should be taken to this menu.'),  # noqa
                                value_type=field.TextLine(title=u"Value"),
                                required=False),
                    )
    records['cpskin.core.interfaces.ICPSkinSettings.contents_in_action_menu'] = record  # noqa


def addShowSloganToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records

    if 'cpskin.core.interfaces.ICPSkinSettings.show_slogan' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.show_slogan to registry')  # noqa
    record = Record(field.Bool(title=_(u'Show slogan with banner'),
                               description=_(u'Show banner title and description as homepage slogan.'),  # noqa
                               required=False,
                               default=False),
                    value=False)
    records['cpskin.core.interfaces.ICPSkinSettings.show_slogan'] = record  # noqa


def addMediaViewletAlbumsToRegistry(value):
    registry = getUtility(IRegistry)
    records = registry.records

    if 'cpskin.core.interfaces.ICPSkinSettings.media_viewlet_visible_albums' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.media_viewlet_visible_albums to registry')  # noqa
    record = Record(field.Int(title=_(u'Viewlet media : Visible albums'),
                               description=_(u'Number of visible albums on media viewlet.'),  # noqa
                               required=False,
                               default=1),
                    value=value)
    records['cpskin.core.interfaces.ICPSkinSettings.media_viewlet_visible_albums'] = record  # noqa


def addMediaViewletVideosToRegistry(value):
    registry = getUtility(IRegistry)
    records = registry.records

    if 'cpskin.core.interfaces.ICPSkinSettings.media_viewlet_visible_videos' in records:
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.media_viewlet_visible_videos to registry')  # noqa
    record = Record(field.Bool(title=_(u'Viewlet media : Visible videos'),
                               description=_(u'Number of visible videos on media viewlet.'),  # noqa
                               required=False,
                               default=1),
                    value=value)
    records['cpskin.core.interfaces.ICPSkinSettings.media_viewlet_visible_videos'] = record  # noqa


def addMediaViewletOptionsToRegistry(upgrade=False):
    registry = getUtility(IRegistry)
    records = registry.records

    value = 1
    if 'cpskin.core.default_visible_albums' in records:
        logger.info('Using existing value for visible_albums')
        value = records['cpskin.core.default_visible_albums'].value
        del records['cpskin.core.default_visible_albums']
    addMediaViewletAlbumsToRegistry(value)

    value = 1
    if upgrade:
        value = 2  # old default value was fixed in Python code
    addMediaViewletVideosToRegistry(value)


def addDescriptionOnThemesOptionToRegistry():
    registry = getUtility(IRegistry)
    records = registry.records

    if 'cpskin.core.interfaces.ICPSkinSettings.show_description_on_themes' in records:  # noqa
        return

    logger.info(
        'Adding cpskin.core.interfaces.ICPSkinSettings.show_description_on_themes to registry')  # noqa
    record = Record(field.Bool(title=_(u'Show description on themes'),
                               description=_(u'Add content description after every portal tab menu title.'),  # noqa
                               required=False,
                               default=False),
                    value=False)
    records['cpskin.core.interfaces.ICPSkinSettings.show_description_on_themes'] = record  # noqa


def set_googleapi_key():
    record_name = 'collective.geo.settings.interfaces.IGeoSettings.googleapi'
    default_value = 'AIzaSyDmbfEFrVcZ_x7Snn4Kv_WkqCmiZXn01rY'
    value = api.portal.get_registry_record(record_name)
    if value == default_value:
        api.portal.set_registry_record(
            record_name, 'ABQIAAAAaKes6QWqobpCx2AOamo-shTwM0brOpm')


def upgrade_front_page():
    portal = api.portal.get()
    if not portal.hasObject('front-page'):
        frontPage = api.content.create(
            container=portal,
            type='Document',
            id='front-page',
            title='Bienvenue chez IMIO'
        )
    else:
        frontPage = getattr(portal, 'front-page', None)
    # if frontPage is not None:
    #     frontPage.setExcludeFromNav(True)
    setPageText(portal, frontPage, 'cpskin-frontpage-setup')
