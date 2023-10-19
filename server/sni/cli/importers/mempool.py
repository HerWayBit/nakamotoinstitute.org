import os

import click

from sni.authors.models import Author
from sni.cli.utils import (
    DONE,
    extract_data_from_filename,
    get,
    process_canonical_file,
    process_translated_file,
)
from sni.extensions import db
from sni.mempool.models import (
    BlogPost,
    BlogPostTranslation,
    BlogSeriesTranslation,
)
from sni.mempool.schemas import (
    MempoolCanonicalMDModel,
    MempoolMDModel,
    MempoolTranslationMDModel,
)
from sni.translators.models import Translator


def process_and_add_canonical_file(
    filepath: str, slug: str, blog_posts: dict, canonical_schema, schema
):
    (
        validated_canonical_data,
        validated_translation_data,
        content,
    ) = process_canonical_file(filepath, canonical_schema, schema)

    canonical_data = validated_canonical_data.dict()
    translation_data = validated_translation_data.dict()

    canonical_data["authors"] = [
        get(Author, slug=author) for author in canonical_data.pop("authors")
    ]
    series = canonical_data.pop("series")
    canonical_data["series"] = (
        get(BlogSeriesTranslation, slug=series).blog_series if series else None
    )
    blog_post = BlogPost(**canonical_data)
    db.session.add(blog_post)
    db.session.flush()

    translation_data["translators"] = [
        get(Translator, slug=slug) for slug in translation_data.pop("translators", [])
    ]
    blog_post_translation = BlogPostTranslation(
        **translation_data,
        slug=slug,
        locale="en",
        content=content,
        blog_post=blog_post,
    )
    db.session.add(blog_post_translation)

    blog_posts[slug] = {"canonical": blog_post, "translation": blog_post_translation}


def process_and_add_translated_file(
    filepath: str, slug: str, locale: str, blog_posts: dict, translated_schema
):
    validated_translation_data, content = process_translated_file(
        filepath, translated_schema
    )

    translation_data = validated_translation_data.dict()
    blog_post = blog_posts.get(slug)

    if not blog_post:
        return

    translation_data["slug"] = translation_data.get("slug") or slug
    translation_data["excerpt"] = (
        translation_data.get("excerpt") or blog_post["translation"].excerpt
    )
    translation_data["translators"] = [
        get(Translator, slug=slug) for slug in translation_data.pop("translators", [])
    ]
    blog_post_translation = BlogPostTranslation(
        **translation_data,
        locale=locale,
        content=content,
        blog_post=blog_post["canonical"],
    )
    db.session.add(blog_post_translation)


def import_content(directory_path: str, canonical_schema, schema, translated_schema):
    blog_posts = {}
    english_filenames = []
    non_english_filenames = []

    for filename in sorted(os.listdir(directory_path)):
        _, locale, _ = extract_data_from_filename(filename)
        if locale == "en":
            english_filenames.append(filename)
        else:
            non_english_filenames.append(filename)

    for filename in english_filenames:
        filepath = os.path.join(directory_path, filename)
        slug, _, _ = extract_data_from_filename(filename)
        process_and_add_canonical_file(
            filepath, slug, blog_posts, canonical_schema, schema
        )

    for filename in non_english_filenames:
        filepath = os.path.join(directory_path, filename)
        slug, locale, _ = extract_data_from_filename(filename)
        process_and_add_translated_file(
            filepath, slug, locale, blog_posts, translated_schema
        )

    db.session.commit()


def import_mempool():
    click.echo("Importing Mempool...", nl=False)
    import_content(
        "content/mempool",
        MempoolCanonicalMDModel,
        MempoolMDModel,
        MempoolTranslationMDModel,
    )
    click.echo(DONE)
