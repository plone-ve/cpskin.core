# -*- coding: utf-8 -*-
from zope import schema
from zope.interface import Interface

from Products.CMFDefault.formlib.schema import EmailLine

from cpskin.locales import CPSkinMessageFactory as _


class ISendToManagerForm(Interface):
    """ Interface for describing the 'sendtomanager' form """

    send_from_address = EmailLine(
        title=_(u'label_send_from',
                default=u'From'),
        description=_(u'help_send_from',
                      default=u'Your email address.'),
        required=True
    )

    comment = schema.Text(
        title=_(u'label_comment',
                default=u'Change request'),
        description=_(u'help_comment',
                      default=u'Report an error or missing information.'),
        required=False
    )


class IBannerActivationView(Interface):
    """ Banner activation """

    can_enable_banner = schema.Bool(
        u'Can enable banner',
        readonly=True
    )
    can_disable_banner = schema.Bool(
        u'Can disable banner',
        readonly=True
    )

    def enable_banner():
        """ Enable banner
        """

    def disable_banner():
        """ Disable banner
        """

    can_enable_local_banner = schema.Bool(
        u'Can enable local banner',
        readonly=True
    )
    can_disable_local_banner = schema.Bool(
        u'Can disable local banner',
        readonly=True
    )

    def enable_local_banner():
        """ Enable local banner
        """

    def disable_local_banner():
        """ Disable local banner
        """


class IMediaActivationView(Interface):
    """ media activation """

    can_enable_media = schema.Bool(
        u'Can enable multimedia viewlet',
        readonly=True
    )
    can_disable_media = schema.Bool(
        u'Can disable multimedia viewlet',
        readonly=True
    )

    def enable_media():
        """ Enable multimedia viewlet
        """

    def disable_media():
        """ Disable multimedia viewlet
        """
