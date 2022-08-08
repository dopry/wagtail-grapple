import graphene
from django.conf import settings
from django.db import models
from home.blocks import StreamFieldBlock
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase

try:
    from wagtail.admin.panels import FieldPanel, InlinePanel
    from wagtail.fields import RichTextField, StreamField
    from wagtail.models import Orderable, Page
except ImportError:
    from wagtail.admin.edit_handlers import (
        FieldPanel,
        InlinePanel,
        RichTextFieldPanel,
        StreamFieldPanel,
    )
    from wagtail.core.fields import RichTextField, StreamField
    from wagtail.core.models import Orderable, Page

try:
    from wagtail.contrib.settings.models import (
        BaseGenericSetting,
        BaseSiteSetting,
        register_setting,
    )
except ImportError:
    # Wagtail < 4.0
    from wagtail.contrib.settings.models import BaseSetting as BaseSiteSetting
    from wagtail.contrib.settings.models import register_setting

    BaseGenericSetting = models.Model

from wagtail.documents.edit_handlers import DocumentChooserPanel
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtail.snippets.edit_handlers import SnippetChooserPanel
from wagtail.snippets.models import register_snippet
from wagtail_headless_preview.models import HeadlessPreviewMixin
from wagtailmedia.edit_handlers import MediaChooserPanel

from grapple.helpers import (
    register_paginated_query_field,
    register_query_field,
    register_singular_query_field,
)
from grapple.middleware import IsAnonymousMiddleware
from grapple.models import (
    GraphQLCollection,
    GraphQLDocument,
    GraphQLForeignKey,
    GraphQLImage,
    GraphQLMedia,
    GraphQLPage,
    GraphQLSnippet,
    GraphQLStreamfield,
    GraphQLString,
    GraphQLTag,
)
from grapple.utils import resolve_paginated_queryset

document_model_string = getattr(
    settings, "WAGTAILDOCS_DOCUMENT_MODEL", "wagtaildocs.Document"
)


@register_singular_query_field("simpleModel")
class SimpleModel(models.Model):
    pass

from wagtail_headless_preview.models import HeadlessPreviewMixin
class HomePage(Page, HeadlessPreviewMixin):
    pass


class AuthorPage(Page, HeadlessPreviewMixin):
    name = models.CharField(max_length=255)

    content_panels = Page.content_panels + [FieldPanel("name")]

    graphql_fields = [GraphQLString("name")]


class BlogPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "BlogPage", related_name="tagged_items", on_delete=models.CASCADE
    )


@register_singular_query_field("first_post", middleware=[IsAnonymousMiddleware])
@register_paginated_query_field("blog_page", middleware=[IsAnonymousMiddleware])
@register_query_field("post", middleware=[IsAnonymousMiddleware])
class BlogPage(HeadlessPreviewMixin, Page):
    date = models.DateField("Post date")
    advert = models.ForeignKey(
        "home.Advert",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image = models.ForeignKey(
        "images.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    book_file = models.ForeignKey(
        document_model_string,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    featured_media = models.ForeignKey(
        "wagtailmedia.Media",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    author = models.ForeignKey(
        AuthorPage, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    summary = RichTextField(blank=True)
    body = StreamField(StreamFieldBlock())
    tags = ClusterTaggableManager(through=BlogPageTag, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        ImageChooserPanel("hero_image"),
        FieldPanel("summary")
        if settings.WAGTAIL_VERSION >= (3, 0)
        else RichTextFieldPanel("summary"),
        FieldPanel("body")
        if settings.WAGTAIL_VERSION >= (3, 0)
        else StreamFieldPanel("body"),
        FieldPanel("tags"),
        InlinePanel("related_links", label="Related links"),
        InlinePanel("authors", label="Authors"),
        FieldPanel("author"),
        SnippetChooserPanel("advert"),
        DocumentChooserPanel("book_file"),
        MediaChooserPanel("featured_media"),
    ]

    @property
    def copy(self):
        return self

    def paginated_authors(self, info, **kwargs):
        return resolve_paginated_queryset(self.authors, info, **kwargs)

    graphql_fields = [
        GraphQLString("date", required=True),
        GraphQLString("summary"),
        GraphQLStreamfield("body"),
        GraphQLTag("tags"),
        GraphQLCollection(
            GraphQLForeignKey,
            "related_links",
            "home.blogpagerelatedlink",
            required=True,
            item_required=True,
        ),
        GraphQLCollection(GraphQLString, "related_urls", source="related_links.url"),
        GraphQLCollection(GraphQLString, "authors", source="authors.person.name"),
        GraphQLCollection(
            GraphQLForeignKey,
            "paginated_authors",
            "home.Author",
            is_paginated_queryset=True,
        ),
        GraphQLSnippet("advert", "home.Advert"),
        GraphQLImage("hero_image"),
        GraphQLDocument("book_file"),
        GraphQLMedia("featured_media"),
        GraphQLForeignKey("copy", "home.BlogPage"),
        GraphQLPage("author"),
    ]


class BlogPageRelatedLink(Orderable):
    page = ParentalKey(BlogPage, on_delete=models.CASCADE, related_name="related_links")
    name = models.CharField(max_length=255)
    url = models.URLField()

    panels = [FieldPanel("name"), FieldPanel("url")]

    graphql_fields = [GraphQLString("name"), GraphQLString("url")]


@register_snippet
class Person(models.Model):
    name = models.CharField(max_length=255)
    job = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    panels = [FieldPanel("name"), FieldPanel("job")]

    graphql_fields = [GraphQLString("name"), GraphQLString("job")]


class Author(Orderable):
    page = ParentalKey(BlogPage, on_delete=models.CASCADE, related_name="authors")
    role = models.CharField(max_length=255)
    person = models.ForeignKey(
        Person, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    panels = [FieldPanel("role"), SnippetChooserPanel("person")]

    graphql_fields = [GraphQLString("role"), GraphQLForeignKey("person", Person)]


@register_snippet
@register_query_field(
    "advert",
    "adverts",
    {"url": graphene.String()},
    required=True,
    plural_required=True,
    plural_item_required=True,
)
class Advert(models.Model):
    url = models.URLField(null=True, blank=True)
    text = models.CharField(max_length=255)

    panels = [FieldPanel("url"), FieldPanel("text")]

    graphql_fields = [GraphQLString("url"), GraphQLString("text")]

    def __str__(self):
        return self.text


@register_setting
class SocialMediaSettings(BaseSiteSetting):
    facebook = models.URLField(help_text="Your Facebook page URL")
    instagram = models.CharField(
        max_length=255, help_text="Your Instagram username, without the @"
    )
    trip_advisor = models.URLField(help_text="Your Trip Advisor page URL")
    youtube = models.URLField(help_text="Your YouTube channel or user account URL")

    graphql_fields = [
        GraphQLString("facebook"),
        GraphQLString("instagram"),
        GraphQLString("trip_advisor"),
        GraphQLString("youtube"),
    ]


# BaseGenericSetting is not supported in Wagtail < 4.0
# For older versions of Wagtail, we swap BaseGenericSetting with models.Model
# BaseGenericSetting doesn't add any fields, so the migrations should be the same
class GlobalSocialMediaSettings(BaseGenericSetting):
    facebook = models.URLField(help_text="Your Facebook page URL")
    instagram = models.CharField(
        max_length=255, help_text="Your Instagram username, without the @"
    )
    trip_advisor = models.URLField(help_text="Your Trip Advisor page URL")
    youtube = models.URLField(help_text="Your YouTube channel or user account URL")

    graphql_fields = [
        GraphQLString("facebook"),
        GraphQLString("instagram"),
        GraphQLString("trip_advisor"),
        GraphQLString("youtube"),
    ]


# Only register it as a setting if BaseGenericSetting exists (on Wagtail 4.0+)
if BaseGenericSetting is not models.Model:
    register_setting(GlobalSocialMediaSettings)
