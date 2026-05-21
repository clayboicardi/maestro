# AUTO-GENERATED from Viren070/AIOStreams@v2.29.6.
# DO NOT EDIT BY HAND - overwritten by scripts/regen_aiostreams_schemas.sh.
# Hand-overlay validators (runtime refinements that don't survive Zod->JSON-Schema
# round-trip) live in schemas.py.

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field, RootModel, constr


class Server(RootModel[str]):
    root: str = Field(..., min_length=1)


class RarUrl(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    url: str
    bytes: float | None = None


class ZipUrl(RarUrl):
    pass


class Field7zipUrl(RarUrl):
    pass


class TgzUrl(RarUrl):
    pass


class TarUrl(RarUrl):
    pass


class Subtitle(BaseModel):
    id: str = Field(..., min_length=1)
    url: str
    lang: str = Field(..., min_length=1)


class Source(RootModel[str]):
    root: str = Field(..., min_length=1)


class CountryWhitelistItem(RootModel[str]):
    root: str = Field(..., max_length=3, min_length=3)


class ProxyHeaders(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    request: dict[constr(min_length=1), str] | None = None
    response: dict[constr(min_length=1), str] | None = None


class BehaviorHints(BaseModel):
    countryWhitelist: list[CountryWhitelistItem] | None = None
    notWebReady: bool | None = None
    bingeGroup: str | None = None
    proxyHeaders: ProxyHeaders | None = None
    videoHash: str | None = None
    videoSize: float | None = None
    filename: str | None = None


class Error(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class Id(StrEnum):
    REALDEBRID = "realdebrid"
    DEBRIDLINK = "debridlink"
    PREMIUMIZE = "premiumize"
    ALLDEBRID = "alldebrid"
    TORBOX = "torbox"
    EASYDEBRID = "easydebrid"
    DEBRIDER = "debrider"
    PUTIO = "putio"
    PIKPAK = "pikpak"
    OFFCLOUD = "offcloud"
    SEEDR = "seedr"
    EASYNEWS = "easynews"
    NZBDAV = "nzbdav"
    ALTMOUNT = "altmount"
    STREMIO_NNTP = "stremio_nntp"
    STREMTHRU_NEWZ = "stremthru_newz"


class Service(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: Id
    cached: bool


class ParsedFile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    releaseGroup: str | None = None
    resolution: str | None = None
    quality: str | None = None
    encode: str | None = None
    audioChannels: list[str]
    visualTags: list[str]
    audioTags: list[str]
    languages: list[str]
    subtitles: list[str] | None = None
    subbed: bool | None = None
    dubbed: bool | None = None
    title: str | None = None
    year: str | None = None
    seasons: list[float] | None = None
    volumes: list[float] | None = None
    folderSeasons: list[float] | None = None
    folderEpisodes: list[float] | None = None
    date: str | None = None
    episodes: list[float] | None = None
    editions: list[str] | None = None
    regraded: bool | None = None
    repack: bool | None = None
    uncensored: bool | None = None
    unrated: bool | None = None
    upscaled: bool | None = None
    network: str | None = None
    container: str | None = None
    extension: str | None = None
    seasonPack: bool | None = None
    hasChapters: bool | None = None


class RegexMatched(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str | None = None
    pattern: str | None = Field(None, min_length=1)
    index: float


class StreamExpressionMatched(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str | None = None
    index: float


class RankedStreamExpressionsMatchedItem(RootModel[str]):
    root: str = Field(..., min_length=1)


class Seadex(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    isBest: bool
    isSeadex: bool


class Type(StrEnum):
    P2P = "p2p"
    LIVE = "live"
    STREMIO_USENET = "stremio-usenet"
    ARCHIVE = "archive"
    USENET = "usenet"
    DEBRID = "debrid"
    HTTP = "http"
    EXTERNAL = "external"
    YOUTUBE = "youtube"
    ERROR = "error"
    STATISTIC = "statistic"
    INFO = "info"


class Torrent(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    infoHash: str | None = Field(None, min_length=1)
    fileIdx: float | None = None
    seeders: float | None = None
    sources: list[Source] | None = None
    private: bool | None = None


class StreamData(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    error: Error | None = None
    proxied: bool | None = None
    addon: str | None = None
    filename: str | None = None
    folderName: str | None = None
    service: Service | None = None
    parsedFile: ParsedFile | None = None
    message: str | None = Field(None, max_length=1000)
    regexMatched: RegexMatched | None = None
    rankedRegexesMatched: list[str] | None = None
    regexScore: float | None = None
    keywordMatched: bool | None = None
    streamExpressionMatched: StreamExpressionMatched | float | None = None
    rankedStreamExpressionsMatched: list[RankedStreamExpressionsMatchedItem] | None = None
    streamExpressionScore: float | None = None
    seadex: Seadex | None = None
    size: float | None = None
    folderSize: float | None = None
    type: Type | None = None
    indexer: str | None = None
    age: float | str | None = None
    nzbUrl: str | None = None
    torrent: Torrent | None = None
    duration: float | None = None
    library: bool | None = None
    id: str | None = Field(None, min_length=1)


class AIOStream(BaseModel):
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = None
    infoHash: str | None = None
    fileIdx: float | None = None
    externalUrl: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    subtitles: list[Subtitle] | None = None
    sources: list[Source] | None = None
    behaviorHints: BehaviorHints | None = None
    streamData: StreamData | None = None


class AIOratingsIsValidResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    valid: bool


class Name(StrEnum):
    STREAM = "stream"
    SUBTITLES = "subtitles"
    CATALOG = "catalog"
    META = "meta"
    ADDON_CATALOG = "addon_catalog"


class Resources(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: Name
    types: list[str]
    idPrefixes: list[str] | None = None


class ExtraItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str = Field(..., min_length=1)
    isRequired: bool | None = None
    options: list[str | None] | None = None
    optionsLimit: float | None = Field(None, ge=1.0)


class Catalog(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: str
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    extra: list[ExtraItem] | None = None


class AddonCatalog(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: str
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class BehaviorHints1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    adult: bool | None = None
    p2p: bool | None = None
    configurable: bool | None = None
    configurationRequired: bool | None = None


class StremioAddonsConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    issuer: str = Field(..., min_length=1)
    signature: str = Field(..., min_length=1)


class Manifest(BaseModel):
    id: str = Field(..., min_length=1)
    name: str
    description: str | None = None
    version: str
    types: list[str]
    idPrefixes: list[str] | None = None
    resources: list[str | Resources]
    catalogs: list[Catalog]
    addonCatalogs: list[AddonCatalog] | None = None
    background: str | None = None
    logo: str | None = None
    contactEmail: str | None = None
    behaviorHints: BehaviorHints1 | None = None
    stremioAddonsConfig: StremioAddonsConfig | None = None


class Addon(BaseModel):
    transportName: Literal["http"]
    transportUrl: AnyUrl
    manifest: Manifest


class AddonCatalogResponseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    addons: list[Addon]


class Resources1(Resources):
    pass


class Catalog1(Catalog):
    pass


class Manifest1(BaseModel):
    id: str = Field(..., min_length=1)
    name: str
    description: str | None = None
    version: str
    types: list[str]
    idPrefixes: list[str] | None = None
    resources: list[str | Resources1]
    catalogs: list[Catalog1]
    addonCatalogs: list[AddonCatalog] | None = None
    background: str | None = None
    logo: str | None = None
    contactEmail: str | None = None
    behaviorHints: BehaviorHints1 | None = None
    stremioAddonsConfig: StremioAddonsConfig | None = None


class AddonCatalogSchema(BaseModel):
    transportName: Literal["http"]
    transportUrl: AnyUrl
    manifest: Manifest1


class StreamType(StrEnum):
    USENET = "usenet"
    TORRENT = "torrent"


class CacheAndPlaySchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    streamTypes: list[StreamType] | None = None


class PosterShape(StrEnum):
    SQUARE = "square"
    POSTER = "poster"
    LANDSCAPE = "landscape"
    REGULAR = "regular"


class Type1(StrEnum):
    TRAILER = "Trailer"
    CLIP = "Clip"
    TEASER = "Teaser"


class Trailer(BaseModel):
    source: str = Field(..., min_length=1)
    type: Type1


class Url(RootModel[str]):
    root: str = Field(..., pattern="^stremio:\\/\\/\\/.*")


class Link(BaseModel):
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    url: AnyUrl | Url


class Meta(BaseModel):
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    name: str | None = None
    poster: str | None = None
    posterShape: PosterShape | None = None
    genres: list[str] | None = None
    imdbRating: str | float | None = None
    releaseInfo: str | float | None = None
    director: list[str | None] | str | None = None
    cast: list[str] | None = None
    description: str | None = None
    trailers: list[Trailer] | None = None
    links: list[Link] | None = None


class CatalogResponseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    metas: list[Meta]


class ExtrasSchema(BaseModel):
    skip: float | None = None
    genre: str | None = None
    search: str | None = None
    filename: str | None = None
    videoHash: str | None = None
    videoSize: float | None = None


class Resources2(Resources):
    pass


class Catalog2(Catalog):
    pass


class ManifestSchema(BaseModel):
    id: str = Field(..., min_length=1)
    name: str
    description: str | None = None
    version: str
    types: list[str]
    idPrefixes: list[str] | None = None
    resources: list[str | Resources2]
    catalogs: list[Catalog2]
    addonCatalogs: list[AddonCatalog] | None = None
    background: str | None = None
    logo: str | None = None
    contactEmail: str | None = None
    behaviorHints: BehaviorHints1 | None = None
    stremioAddonsConfig: StremioAddonsConfig | None = None


class Trailer1(Trailer):
    pass


class Link1(Link):
    pass


class MetaPreviewSchema(BaseModel):
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    name: str | None = None
    poster: str | None = None
    posterShape: PosterShape | None = None
    genres: list[str] | None = None
    imdbRating: str | float | None = None
    releaseInfo: str | float | None = None
    director: list[str | None] | str | None = None
    cast: list[str] | None = None
    description: str | None = None
    trailers: list[Trailer1] | None = None
    links: list[Link1] | None = None


class Trailer2(Trailer):
    pass


class Link2(Link):
    pass


class Released(RootModel[AwareDatetime]):
    root: AwareDatetime = Field(
        ...,
        pattern="^(?:(?:\\d\\d[2468][048]|\\d\\d[13579][26]|\\d\\d0[48]|[02468][048]00|[13579][26]00)-02-29|\\d{4}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12]\\d|3[01])|(?:0[469]|11)-(?:0[1-9]|[12]\\d|30)|(?:02)-(?:0[1-9]|1\\d|2[0-8])))T(?:(?:[01]\\d|2[0-3]):[0-5]\\d(?::[0-5]\\d(?:\\.\\d+)?)?(?:Z))$",
    )


class BehaviorHints4(BehaviorHints):
    pass


class Stream(BaseModel):
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = None
    infoHash: str | None = None
    fileIdx: float | None = None
    externalUrl: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    subtitles: list[Subtitle] | None = None
    sources: list[Source] | None = None
    behaviorHints: BehaviorHints4 | None = None


class Trailer3(Trailer):
    pass


class Video(BaseModel):
    id: str
    title: str | None = None
    name: str | None = None
    released: Released | None = None
    thumbnail: str | None = None
    streams: list[Stream] | None = None
    available: bool | None = None
    episode: float | None = None
    season: float | None = None
    trailers: list[Trailer3] | None = None
    overview: str | None = None


class BehaviorHints5(BaseModel):
    defaultVideoId: str | None = None
    hasScheduledVideo: bool | None = None


class Meta1(BaseModel):
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    name: str | None = None
    poster: str | None = None
    posterShape: PosterShape | None = None
    genres: list[str] | None = None
    imdbRating: str | float | None = None
    releaseInfo: str | float | None = None
    director: list[str | None] | str | None = None
    cast: list[str] | None = None
    description: str | None = None
    trailers: list[Trailer2] | None = None
    links: list[Link2] | None = None
    background: str | None = None
    logo: str | None = None
    videos: list[Video] | None = None
    runtime: str | None = None
    language: str | None = None
    country: str | None = None
    awards: str | None = None
    website: AnyUrl | None = None
    behaviorHints: BehaviorHints5 | None = None


class MetaResponseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    meta: Meta1


class Trailer4(Trailer):
    pass


class Link3(Link):
    pass


class BehaviorHints6(BehaviorHints):
    pass


class Stream1(BaseModel):
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = None
    infoHash: str | None = None
    fileIdx: float | None = None
    externalUrl: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    subtitles: list[Subtitle] | None = None
    sources: list[Source] | None = None
    behaviorHints: BehaviorHints6 | None = None


class Trailer5(Trailer):
    pass


class Video1(BaseModel):
    id: str
    title: str | None = None
    name: str | None = None
    released: Released | None = None
    thumbnail: str | None = None
    streams: list[Stream1] | None = None
    available: bool | None = None
    episode: float | None = None
    season: float | None = None
    trailers: list[Trailer5] | None = None
    overview: str | None = None


class BehaviorHints7(BehaviorHints5):
    pass


class MetaSchema(BaseModel):
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    name: str | None = None
    poster: str | None = None
    posterShape: PosterShape | None = None
    genres: list[str] | None = None
    imdbRating: str | float | None = None
    releaseInfo: str | float | None = None
    director: list[str | None] | str | None = None
    cast: list[str] | None = None
    description: str | None = None
    trailers: list[Trailer4] | None = None
    links: list[Link3] | None = None
    background: str | None = None
    logo: str | None = None
    videos: list[Video1] | None = None
    runtime: str | None = None
    language: str | None = None
    country: str | None = None
    awards: str | None = None
    website: AnyUrl | None = None
    behaviorHints: BehaviorHints7 | None = None


class NNTPServersSchemaItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    username: str
    password: str
    host: str
    port: float
    ssl: bool
    connections: float


class OpenPosterDBIsValidResponse(AIOratingsIsValidResponse):
    pass


class Presets(StrEnum):
    INHERIT = "inherit"
    EXTEND = "extend"
    OVERRIDE = "override"


class Filters(StrEnum):
    INHERIT = "inherit"
    OVERRIDE = "override"


class FieldOverrides(StrEnum):
    INHERIT = "inherit"
    OVERRIDE = "override"
    EXTEND = "extend"


class MergeStrategies(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    presets: Presets
    services: Presets
    filters: Filters
    sorting: Filters
    formatter: Filters
    proxy: Filters
    metadata: Filters
    misc: Filters
    branding: Filters
    fieldOverrides: dict[str, FieldOverrides] | None = None


class ParentConfigSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    uuid: UUID = Field(
        ...,
        pattern="^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
    )
    password: str = Field(..., min_length=1)
    mergeStrategies: MergeStrategies | None = None


class ParsedFileSchema(ParsedFile):
    pass


class Trailer6(Trailer):
    pass


class Link4(Link):
    pass


class Preset(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str
    type: str
    options: dict[str, Any]


class MediaType(StrEnum):
    MOVIE = "movie"
    SERIES = "series"
    CHANNEL = "channel"
    TV = "tv"
    ANIME = "anime"


class PinPosition(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"


class Addon1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    instanceId: str | None = Field(None, min_length=1)
    preset: Preset
    manifestUrl: AnyUrl
    enabled: bool
    resources: list[Name] | None = None
    mediaTypes: list[MediaType] | None = None
    name: str
    identifier: str | None = None
    displayIdentifier: str | None = None
    timeout: float = Field(..., ge=1.0)
    library: bool | None = None
    formatPassthrough: bool | None = None
    resultPassthrough: bool | None = None
    pinPosition: PinPosition | None = None
    serviceWrapped: bool | None = None
    headers: dict[constr(min_length=1), str] | None = None
    ip: str | None = None


class Torrent1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    infoHash: str | None = Field(None, min_length=1)
    fileIdx: float | None = None
    seeders: float | None = None
    sources: list[Source] | None = None
    private: bool | None = None
    freeleech: bool | None = None


class Service1(Service):
    pass


class PassthroughEnum(StrEnum):
    FILTER = "filter"
    LANGUAGE = "language"
    SUBTITLE = "subtitle"
    DEDUP = "dedup"
    LIMIT = "limit"
    EXCLUDED = "excluded"
    REQUIRED = "required"
    TITLE = "title"
    YEAR = "year"
    EPISODE = "episode"
    DIGITAL_RELEASE = "digitalRelease"


class Passthrough(RootModel[list[PassthroughEnum]]):
    root: list[PassthroughEnum] = Field(..., min_length=1)


class Stream2(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., min_length=1)
    proxied: bool | None = None
    addon: Addon1
    parsedFile: ParsedFile | None = None
    message: str | None = Field(None, max_length=1000)
    regexMatched: RegexMatched | None = None
    rankedRegexesMatched: list[str] | None = None
    regexScore: float | None = None
    keywordMatched: bool | None = None
    streamExpressionMatched: StreamExpressionMatched | None = None
    rankedStreamExpressionsMatched: list[RankedStreamExpressionsMatchedItem] | None = None
    streamExpressionScore: float | None = None
    size: float | None = None
    folderSize: float | None = None
    type: Type
    indexer: str | None = None
    age: float | None = None
    torrent: Torrent1 | None = None
    countryWhitelist: list[CountryWhitelistItem] | None = None
    notWebReady: bool | None = None
    bingeGroup: str | None = Field(None, min_length=1)
    requestHeaders: dict[constr(min_length=1), str] | None = None
    responseHeaders: dict[constr(min_length=1), str] | None = None
    videoHash: str | None = Field(None, min_length=1)
    subtitles: list[Subtitle] | None = None
    filename: str | None = None
    folderName: str | None = None
    service: Service1 | None = None
    duration: float | None = None
    bitrate: float | None = None
    library: bool | None = None
    seadex: Seadex | None = None
    passthrough: Literal[True] | Passthrough | None = None
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = Field(None, min_length=1)
    externalUrl: str | None = Field(None, min_length=1)
    error: Error | None = None
    originalName: str | None = None
    originalDescription: str | None = None
    extra: dict[str, Any] | None = None


class Trailer7(Trailer):
    pass


class Video2(BaseModel):
    id: str
    title: str | None = None
    name: str | None = None
    released: Released | None = None
    thumbnail: str | None = None
    streams: list[Stream2] | None = None
    available: bool | None = None
    episode: float | None = None
    season: float | None = None
    trailers: list[Trailer7] | None = None
    overview: str | None = None


class ParsedMetaSchema(BaseModel):
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    name: str | None = None
    poster: str | None = None
    posterShape: PosterShape | None = None
    genres: list[str] | None = None
    imdbRating: str | float | None = None
    releaseInfo: str | float | None = None
    director: list[str | None] | str | None = None
    cast: list[str] | None = None
    description: str | None = None
    trailers: list[Trailer6] | None = None
    links: list[Link4] | None = None
    background: str | None = None
    logo: str | None = None
    videos: list[Video2] | None = None
    runtime: str | None = None
    language: str | None = None
    country: str | None = None
    awards: str | None = None
    website: AnyUrl | None = None
    behaviorHints: BehaviorHints7 | None = None


class Addon2(Addon1):
    pass


class Torrent2(Torrent1):
    pass


class Service2(Service):
    pass


class Passthrough1(RootModel[list[PassthroughEnum]]):
    root: list[PassthroughEnum] = Field(..., min_length=1)


class ParsedStreamSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., min_length=1)
    proxied: bool | None = None
    addon: Addon2
    parsedFile: ParsedFile | None = None
    message: str | None = Field(None, max_length=1000)
    regexMatched: RegexMatched | None = None
    rankedRegexesMatched: list[str] | None = None
    regexScore: float | None = None
    keywordMatched: bool | None = None
    streamExpressionMatched: StreamExpressionMatched | None = None
    rankedStreamExpressionsMatched: list[RankedStreamExpressionsMatchedItem] | None = None
    streamExpressionScore: float | None = None
    size: float | None = None
    folderSize: float | None = None
    type: Type
    indexer: str | None = None
    age: float | None = None
    torrent: Torrent2 | None = None
    countryWhitelist: list[CountryWhitelistItem] | None = None
    notWebReady: bool | None = None
    bingeGroup: str | None = Field(None, min_length=1)
    requestHeaders: dict[constr(min_length=1), str] | None = None
    responseHeaders: dict[constr(min_length=1), str] | None = None
    videoHash: str | None = Field(None, min_length=1)
    subtitles: list[Subtitle] | None = None
    filename: str | None = None
    folderName: str | None = None
    service: Service2 | None = None
    duration: float | None = None
    bitrate: float | None = None
    library: bool | None = None
    seadex: Seadex | None = None
    passthrough: Literal[True] | Passthrough1 | None = None
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = Field(None, min_length=1)
    externalUrl: str | None = Field(None, min_length=1)
    error: Error | None = None
    originalName: str | None = None
    originalDescription: str | None = None
    extra: dict[str, Any] | None = None


class Addon3(Addon1):
    pass


class Torrent3(Torrent1):
    pass


class Service3(Service):
    pass


class Passthrough2(RootModel[list[PassthroughEnum]]):
    root: list[PassthroughEnum] = Field(..., min_length=1)


class ParsedStream(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., min_length=1)
    proxied: bool | None = None
    addon: Addon3
    parsedFile: ParsedFile | None = None
    message: str | None = Field(None, max_length=1000)
    regexMatched: RegexMatched | None = None
    rankedRegexesMatched: list[str] | None = None
    regexScore: float | None = None
    keywordMatched: bool | None = None
    streamExpressionMatched: StreamExpressionMatched | None = None
    rankedStreamExpressionsMatched: list[RankedStreamExpressionsMatchedItem] | None = None
    streamExpressionScore: float | None = None
    size: float | None = None
    folderSize: float | None = None
    type: Type
    indexer: str | None = None
    age: float | None = None
    torrent: Torrent3 | None = None
    countryWhitelist: list[CountryWhitelistItem] | None = None
    notWebReady: bool | None = None
    bingeGroup: str | None = Field(None, min_length=1)
    requestHeaders: dict[constr(min_length=1), str] | None = None
    responseHeaders: dict[constr(min_length=1), str] | None = None
    videoHash: str | None = Field(None, min_length=1)
    subtitles: list[Subtitle] | None = None
    filename: str | None = None
    folderName: str | None = None
    service: Service3 | None = None
    duration: float | None = None
    bitrate: float | None = None
    library: bool | None = None
    seadex: Seadex | None = None
    passthrough: Literal[True] | Passthrough2 | None = None
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = Field(None, min_length=1)
    externalUrl: str | None = Field(None, min_length=1)
    error: Error | None = None
    originalName: str | None = None
    originalDescription: str | None = None
    extra: dict[str, Any] | None = None


class RPDBIsValidResponse(AIOratingsIsValidResponse):
    pass


class SourceSchema(RarUrl):
    pass


class BehaviorHints9(BehaviorHints):
    pass


class Stream3(BaseModel):
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = None
    infoHash: str | None = None
    fileIdx: float | None = None
    externalUrl: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    subtitles: list[Subtitle] | None = None
    sources: list[Source] | None = None
    behaviorHints: BehaviorHints9 | None = None


class StreamResponseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    streams: list[Stream3]


class BehaviorHints10(BehaviorHints):
    pass


class StreamSchema(BaseModel):
    url: str | None = None
    nzbUrl: str | None = None
    servers: list[Server] | None = None
    rarUrls: list[RarUrl] | None = None
    zipUrls: list[ZipUrl] | None = None
    field_7zipUrls: list[Field7zipUrl] | None = Field(None, alias="7zipUrls")
    tgzUrls: list[TgzUrl] | None = None
    tarUrls: list[TarUrl] | None = None
    ytId: str | None = None
    infoHash: str | None = None
    fileIdx: float | None = None
    externalUrl: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    subtitles: list[Subtitle] | None = None
    sources: list[Source] | None = None
    behaviorHints: BehaviorHints10 | None = None


class SubtitleResponseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    subtitles: list[Subtitle]


class SubtitleSchema(Subtitle):
    pass


class Source9(StrEnum):
    BUILTIN = "builtin"
    CUSTOM = "custom"
    EXTERNAL = "external"


class ChangelogItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    date: str
    version: str
    content: str


class TopPosterIsValidResponse(AIOratingsIsValidResponse):
    pass


class MergeStrategies1(MergeStrategies):
    pass


class ParentConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    uuid: UUID = Field(
        ...,
        pattern="^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
    )
    password: str = Field(..., min_length=1)
    mergeStrategies: MergeStrategies1 | None = None


class AppliedTemplate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str
    version: str
    url: str | None = None
    dismissedVersion: str | None = None
    ignored: bool | None = None


class ExcludedResolution(StrEnum):
    FIELD_2160P = "2160p"
    FIELD_1440P = "1440p"
    FIELD_1080P = "1080p"
    FIELD_720P = "720p"
    FIELD_576P = "576p"
    FIELD_480P = "480p"
    FIELD_360P = "360p"
    FIELD_240P = "240p"
    FIELD_144P = "144p"
    UNKNOWN = "Unknown"


class ExcludedQuality(StrEnum):
    BLU_RAY_REMUX = "BluRay REMUX"
    BLU_RAY = "BluRay"
    WEB_DL = "WEB-DL"
    WEB_RIP = "WEBRip"
    HD_RIP = "HDRip"
    HC_HD_RIP = "HC HD-Rip"
    DVD_RIP = "DVDRip"
    HDTV = "HDTV"
    CAM = "CAM"
    TS = "TS"
    TC = "TC"
    SCR = "SCR"
    UNKNOWN = "Unknown"


class ExcludedLanguage(StrEnum):
    ENGLISH = "English"
    JAPANESE = "Japanese"
    CHINESE = "Chinese"
    RUSSIAN = "Russian"
    ARABIC = "Arabic"
    PORTUGUESE = "Portuguese"
    PORTUGUESE__BRAZIL_ = "Portuguese (Brazil)"
    SPANISH = "Spanish"
    FRENCH = "French"
    GERMAN = "German"
    ITALIAN = "Italian"
    KOREAN = "Korean"
    HINDI = "Hindi"
    BENGALI = "Bengali"
    PUNJABI = "Punjabi"
    MARATHI = "Marathi"
    GUJARATI = "Gujarati"
    TAMIL = "Tamil"
    TELUGU = "Telugu"
    KANNADA = "Kannada"
    MALAYALAM = "Malayalam"
    THAI = "Thai"
    VIETNAMESE = "Vietnamese"
    INDONESIAN = "Indonesian"
    TURKISH = "Turkish"
    HEBREW = "Hebrew"
    PERSIAN = "Persian"
    UKRAINIAN = "Ukrainian"
    GREEK = "Greek"
    LITHUANIAN = "Lithuanian"
    LATVIAN = "Latvian"
    ESTONIAN = "Estonian"
    POLISH = "Polish"
    CZECH = "Czech"
    SLOVAK = "Slovak"
    HUNGARIAN = "Hungarian"
    ROMANIAN = "Romanian"
    BULGARIAN = "Bulgarian"
    SERBIAN = "Serbian"
    CROATIAN = "Croatian"
    SLOVENIAN = "Slovenian"
    DUTCH = "Dutch"
    DANISH = "Danish"
    FINNISH = "Finnish"
    SWEDISH = "Swedish"
    NORWEGIAN = "Norwegian"
    MALAY = "Malay"
    LATINO = "Latino"
    DUAL_AUDIO = "Dual Audio"
    DUBBED = "Dubbed"
    MULTI = "Multi"
    ORIGINAL = "Original"
    UNKNOWN = "Unknown"


class ExcludedVisualTag(StrEnum):
    HDR_DV = "HDR+DV"
    DV_ONLY = "DV Only"
    HDR_ONLY = "HDR Only"
    HDR10_ = "HDR10+"
    HDR10 = "HDR10"
    DV = "DV"
    HDR = "HDR"
    HLG = "HLG"
    FIELD_10BIT = "10bit"
    FIELD_3_D = "3D"
    IMAX = "IMAX"
    AI = "AI"
    SDR = "SDR"
    H_OU = "H-OU"
    H_SBS = "H-SBS"
    UNKNOWN = "Unknown"


class ExcludedAudioTag(StrEnum):
    ATMOS = "Atmos"
    DD_ = "DD+"
    DD = "DD"
    DTS_X = "DTS:X"
    DTS_HD_MA = "DTS-HD MA"
    DTS_HD = "DTS-HD"
    DTS_ES = "DTS-ES"
    DTS = "DTS"
    TRUE_HD = "TrueHD"
    OPUS = "OPUS"
    FLAC = "FLAC"
    AAC = "AAC"
    UNKNOWN = "Unknown"


class ExcludedAudioChannel(StrEnum):
    FIELD_2_0 = "2.0"
    FIELD_5_1 = "5.1"
    FIELD_6_1 = "6.1"
    FIELD_7_1 = "7.1"
    UNKNOWN = "Unknown"


class ExcludedEncode(StrEnum):
    AV1 = "AV1"
    HEVC = "HEVC"
    AVC = "AVC"
    XVI_D = "XviD"
    DIV_X = "DivX"
    UNKNOWN = "Unknown"


class ExcludedRegexPattern(RootModel[str]):
    root: str = Field(..., min_length=1)


class IncludedRegexPattern(RootModel[str]):
    root: str = Field(..., min_length=1)


class RequiredRegexPattern(RootModel[str]):
    root: str = Field(..., min_length=1)


class PreferredRegexPattern(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str = Field(..., min_length=0)
    pattern: str = Field(..., min_length=1)


class ExcludedReleaseGroup(RootModel[str]):
    root: str = Field(..., min_length=1)


class IncludedReleaseGroup(RootModel[str]):
    root: str = Field(..., min_length=1)


class RequiredReleaseGroup(RootModel[str]):
    root: str = Field(..., min_length=1)


class PreferredReleaseGroup(RootModel[str]):
    root: str = Field(..., min_length=1)


class RequiredKeyword(RootModel[str]):
    root: str = Field(..., min_length=1)


class IncludedKeyword(RootModel[str]):
    root: str = Field(..., min_length=1)


class ExcludedKeyword(RootModel[str]):
    root: str = Field(..., min_length=1)


class PreferredKeyword(RootModel[str]):
    root: str = Field(..., min_length=1)


class SeederRangeType(StrEnum):
    P2P = "p2p"
    CACHED = "cached"
    UNCACHED = "uncached"


class AgeRangeType(StrEnum):
    USENET = "usenet"
    DEBRID = "debrid"
    P2P = "p2p"


class DigitalReleaseFilter(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    tolerance: float | None = Field(None, ge=0.0, le=365.0)
    requestTypes: list[str] | None = None
    addons: list[str] | None = None
    showInfoOnFilter: bool | None = None


class ExcludeCachedFromAddon(RootModel[str]):
    root: str = Field(..., min_length=1)


class ExcludeCachedFromService(RootModel[str]):
    root: str = Field(..., min_length=1)


class ExcludeCachedMode(StrEnum):
    OR = "or"
    AND = "and"


class ExcludeUncachedFromAddon(RootModel[str]):
    root: str = Field(..., min_length=1)


class ExcludeUncachedFromService(RootModel[str]):
    root: str = Field(..., min_length=1)


class ExcludedStreamExpression(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    expression: str = Field(..., max_length=3000, min_length=1)
    enabled: bool


class RequiredStreamExpression(ExcludedStreamExpression):
    pass


class PreferredStreamExpression(ExcludedStreamExpression):
    pass


class IncludedStreamExpression(ExcludedStreamExpression):
    pass


class RankedStreamExpression(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    expression: str = Field(..., max_length=3000, min_length=1)
    score: float = Field(..., ge=-1000000.0, le=1000000.0)
    enabled: bool


class RankedRegexPattern(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    pattern: str = Field(..., min_length=1)
    name: str | None = None
    score: float = Field(..., ge=-1000000.0, le=1000000.0)


class RegexOverride(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    pattern: str = Field(..., min_length=1)
    name: str | None = None
    score: float | None = Field(None, ge=-1000000.0, le=1000000.0)
    originalName: str | None = None
    disabled: bool | None = None


class SelOverride(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    expression: str = Field(..., min_length=1)
    score: float | None = Field(None, ge=-1000000.0, le=1000000.0)
    exprNames: list[str] | None = None
    disabled: bool | None = None


class DynamicAddonFetching(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    condition: str | None = Field(None, max_length=3000)


class Addon4(RootModel[str]):
    root: str = Field(..., min_length=1)


class Grouping(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    addons: list[Addon4]
    condition: str = Field(..., max_length=3000, min_length=1)


class Behaviour(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class Groups(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    groupings: list[Grouping] | None = None
    behaviour: Behaviour | None = None


class Key(StrEnum):
    QUALITY = "quality"
    RESOLUTION = "resolution"
    LANGUAGE = "language"
    SUBTITLE = "subtitle"
    VISUAL_TAG = "visualTag"
    AUDIO_TAG = "audioTag"
    AUDIO_CHANNEL = "audioChannel"
    STREAM_TYPE = "streamType"
    ENCODE = "encode"
    SIZE = "size"
    SERVICE = "service"
    SEEDERS = "seeders"
    PRIVATE = "private"
    AGE = "age"
    ADDON = "addon"
    REGEX_PATTERNS = "regexPatterns"
    CACHED = "cached"
    LIBRARY = "library"
    KEYWORD = "keyword"
    STREAM_EXPRESSION_MATCHED = "streamExpressionMatched"
    STREAM_EXPRESSION_SCORE = "streamExpressionScore"
    REGEX_SCORE = "regexScore"
    SEADEX = "seadex"
    BITRATE = "bitrate"
    RELEASE_GROUP = "releaseGroup"


class Direction(StrEnum):
    ASC = "asc"
    DESC = "desc"


class GlobalItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    key: Key
    direction: Direction


class Movie(GlobalItem):
    pass


class Series(GlobalItem):
    pass


class AnimeItem(GlobalItem):
    pass


class CachedItem(GlobalItem):
    pass


class UncachedItem(GlobalItem):
    pass


class CachedMovy(GlobalItem):
    pass


class UncachedMovy(GlobalItem):
    pass


class CachedSery(GlobalItem):
    pass


class UncachedSery(GlobalItem):
    pass


class CachedAnimeItem(GlobalItem):
    pass


class UncachedAnimeItem(GlobalItem):
    pass


class SortCriteria(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    global_: list[GlobalItem] = Field(..., alias="global")
    movies: list[Movie] | None = None
    series: list[Series] | None = None
    anime: list[AnimeItem] | None = None
    cached: list[CachedItem] | None = None
    uncached: list[UncachedItem] | None = None
    cachedMovies: list[CachedMovy] | None = None
    uncachedMovies: list[UncachedMovy] | None = None
    cachedSeries: list[CachedSery] | None = None
    uncachedSeries: list[UncachedSery] | None = None
    cachedAnime: list[CachedAnimeItem] | None = None
    uncachedAnime: list[UncachedAnimeItem] | None = None


class PosterService(StrEnum):
    RPDB = "rpdb"
    TOP_POSTER = "top-poster"
    AIORATINGS = "aioratings"
    OPENPOSTERDB = "openposterdb"
    NONE = "none"


class Id4(StrEnum):
    GDRIVE = "gdrive"
    PRISM = "prism"
    TAMTARO = "tamtaro"
    LIGHTGDRIVE = "lightgdrive"
    MINIMALISTICGDRIVE = "minimalisticgdrive"
    TORRENTIO = "torrentio"
    TORBOX = "torbox"
    CUSTOM = "custom"


class Custom(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str = Field(..., max_length=5000)
    description: str = Field(..., max_length=5000)


class Overrides(Custom):
    pass


class Saved(Custom):
    pass


class Definitions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    custom: Custom | None = None
    overrides: dict[str, Overrides] | None = None
    saved: dict[str, Saved] | None = None


class Formatter2(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: Id4
    definitions: Definitions | None = None


class Id5(StrEnum):
    BUILTIN = "builtin"
    STREMTHRU = "stremthru"
    MEDIAFLOW = "mediaflow"


class ProxiedAddon(RootModel[str]):
    root: str = Field(..., min_length=1)


class ProxiedService(RootModel[str]):
    root: str = Field(..., min_length=1)


class Proxy2(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    id: Id5 | None = None
    url: str | None = None
    publicUrl: str | None = None
    credentials: str | None = None
    publicIp: str | None = None
    proxiedAddons: list[ProxiedAddon] | None = None
    proxiedServices: list[ProxiedService] | None = None


class Mode(StrEnum):
    INDEPENDENT = "independent"
    CONJUNCTIVE = "conjunctive"


class ResultLimits(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    global_: float | None = Field(None, alias="global", ge=1.0)
    service: float | None = Field(None, ge=1.0)
    addon: float | None = Field(None, ge=1.0)
    resolution: float | None = Field(None, ge=1.0)
    quality: float | None = Field(None, ge=1.0)
    streamType: float | None = Field(None, ge=1.0)
    indexer: float | None = Field(None, ge=1.0)
    releaseGroup: float | None = Field(None, ge=1.0)
    mode: Mode | None = None


class Global(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    movies: list[Any] | None = None
    series: list[Any] | None = None
    anime: list[Any] | None = None


class Resolution(Global):
    pass


class Size(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    global_: Global | None = Field(None, alias="global")
    resolution: (
        dict[
            Literal[
                "2160p", "1440p", "1080p", "720p", "576p", "480p", "360p", "240p", "144p", "Unknown"
            ],
            Resolution,
        ]
        | None
    ) = None


class Bitrate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    useMetadataRuntime: bool
    global_: Global | None = Field(None, alias="global")
    resolution: (
        dict[
            Literal[
                "2160p", "1440p", "1080p", "720p", "576p", "480p", "360p", "240p", "144p", "Unknown"
            ],
            Resolution,
        ]
        | None
    ) = None


class StatsToShowEnum(StrEnum):
    ADDON = "addon"
    FILTER = "filter"
    TIMING = "timing"


class Statistics(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    position: PinPosition | None = None
    statsToShow: list[StatsToShowEnum] | None = None
    showFilterStatsOnNoStreams: bool | None = None


class YearMatching(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    tolerance: float | None = Field(None, ge=0.0, le=100.0)
    strict: bool | None = None
    useInitialAirDate: bool | None = None
    requestTypes: list[str] | None = None
    addons: list[str] | None = None


class Mode1(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"


class TitleMatching(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    mode: Mode1 | None = None
    matchYear: bool | None = None
    yearTolerance: float | None = Field(None, ge=0.0, le=100.0)
    similarityThreshold: float | None = Field(None, ge=0.0, le=1.0)
    enabled: bool | None = None
    requestTypes: list[str] | None = None
    addons: list[str] | None = None


class SeasonEpisodeMatching(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    strict: bool | None = None
    requestTypes: list[str] | None = None
    addons: list[str] | None = None


class ExcludeAddon(RootModel[str]):
    root: str = Field(..., min_length=1)


class MultiGroupBehaviour(StrEnum):
    KEEP_ALL = "keep_all"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"


class Key12(StrEnum):
    FILENAME = "filename"
    INFO_HASH = "infoHash"
    SMART_DETECT = "smartDetect"


class Cached(StrEnum):
    SINGLE_RESULT = "single_result"
    PER_SERVICE = "per_service"
    PER_ADDON = "per_addon"
    DISABLED = "disabled"


class SmartDetectAttribute(StrEnum):
    SIZE = "size"
    BITRATE = "bitrate"
    RESOLUTION = "resolution"
    QUALITY = "quality"
    ENCODE = "encode"
    RELEASE_GROUP = "releaseGroup"
    EDITION = "edition"
    REMASTERED = "remastered"
    NETWORK = "network"
    CONTAINER = "container"
    VISUAL_TAGS = "visualTags"
    AUDIO_TAGS = "audioTags"
    AUDIO_CHANNELS = "audioChannels"
    LANGUAGES = "languages"


class LibraryBehaviour(StrEnum):
    IGNORE = "ignore"
    PREFER = "prefer"
    EXCLUSIVE = "exclusive"


class Deduplicator(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    excludeAddons: list[ExcludeAddon] | None = None
    multiGroupBehaviour: MultiGroupBehaviour | None = None
    keys: list[Key12] | None = None
    cached: Cached | None = None
    uncached: Cached | None = None
    p2p: Cached | None = None
    http: Cached | None = None
    live: Cached | None = None
    youtube: Cached | None = None
    external: Cached | None = None
    smartDetectAttributes: list[SmartDetectAttribute] | None = None
    smartDetectRounding: float | None = Field(None, ge=1.0, le=50.0)
    libraryBehaviour: LibraryBehaviour | None = None


class Method(StrEnum):
    MATCHING_FILE = "matchingFile"
    MATCHING_INDEX = "matchingIndex"
    FIRST_FILE = "firstFile"


class Attribute(StrEnum):
    SERVICE = "service"
    ADDON = "addon"
    PROXIED = "proxied"
    RESOLUTION = "resolution"
    QUALITY = "quality"
    ENCODE = "encode"
    AUDIO_TAGS = "audioTags"
    VISUAL_TAGS = "visualTags"
    LANGUAGES = "languages"
    RELEASE_GROUP = "releaseGroup"
    TYPE = "type"
    INFO_HASH = "infoHash"
    SIZE = "size"


class AutoPlay(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    method: Method | None = None
    attributes: list[Attribute] | None = None


class AreYouStillThere(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    episodesBeforeCheck: float | None = Field(None, ge=1.0)
    cooldownMinutes: float | None = Field(None, ge=1.0)


class PreloadStreams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    selector: str | None = Field(None, max_length=3000, min_length=1)
    singleStream: bool | None = None


class Service5(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: Id
    enabled: bool | None = None
    credentials: dict[constr(min_length=1), str]


class Preset3(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: str = Field(..., min_length=1)
    instanceId: str = Field(..., min_length=1)
    enabled: bool
    options: dict[constr(min_length=1), Any]
    category: str | None = None


class CatalogModification(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    name: str | None = None
    shuffle: bool | None = None
    reverse: bool | None = None
    persistShuffleFor: float | None = Field(None, ge=0.0, le=24.0)
    onlyOnDiscover: bool | None = None
    disableSearch: bool | None = None
    onlyOnSearch: bool | None = None
    enabled: bool | None = None
    usePosterService: bool | None = None
    overrideType: str | None = Field(None, min_length=1)
    hideable: bool | None = None
    searchable: bool | None = None
    addonName: str | None = None


class CatalogId(RootModel[str]):
    root: str = Field(..., min_length=1)


class DeduplicationMethod(StrEnum):
    ID = "id"
    TITLE = "title"


class MergeMethod(StrEnum):
    SEQUENTIAL = "sequential"
    INTERLEAVE = "interleave"
    IMDB_RATING = "imdbRating"
    RELEASE_DATE_ASC = "releaseDateAsc"
    RELEASE_DATE_DESC = "releaseDateDesc"


class MergedCatalog(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    catalogIds: list[CatalogId]
    enabled: bool | None = None
    deduplicationMethods: list[DeduplicationMethod] | None = None
    mergeMethod: MergeMethod | None = None


class CacheAndPlay(CacheAndPlaySchema):
    pass


class Position1(StrEnum):
    BEFORE_LIMITING = "beforeLimiting"
    BEFORE_SEL = "beforeSEL"
    LAST = "last"


class NzbFailover(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    count: float | None = Field(None, ge=1.0)
    position: Position1 | None = None


class Preset4(RootModel[str]):
    root: str = Field(..., min_length=1)


class ServiceWrap(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    enabled: bool | None = None
    presets: list[Preset4] | None = None
    services: list[Id] | None = None
    reconfigureService: bool | None = None


class UserDataSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    uuid: UUID | None = Field(
        None,
        pattern="^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
    )
    parentConfig: ParentConfig | None = None
    encryptedPassword: str | None = Field(None, min_length=1)
    trusted: bool | None = None
    showChanges: bool | None = None
    addonPassword: str | None = None
    ip: str | None = None
    addonName: str | None = Field(None, max_length=300, min_length=1)
    addonLogo: AnyUrl | None = None
    addonBackground: AnyUrl | None = None
    addonDescription: str | None = Field(None, min_length=1)
    appliedTemplates: list[AppliedTemplate] | None = None
    excludedResolutions: list[ExcludedResolution] | None = None
    includedResolutions: list[ExcludedResolution] | None = None
    requiredResolutions: list[ExcludedResolution] | None = None
    preferredResolutions: list[ExcludedResolution] | None = None
    excludedQualities: list[ExcludedQuality] | None = None
    includedQualities: list[ExcludedQuality] | None = None
    requiredQualities: list[ExcludedQuality] | None = None
    preferredQualities: list[ExcludedQuality] | None = None
    excludedLanguages: list[ExcludedLanguage] | None = None
    includedLanguages: list[ExcludedLanguage] | None = None
    requiredLanguages: list[ExcludedLanguage] | None = None
    preferredLanguages: list[ExcludedLanguage] | None = None
    excludedSubtitles: list[ExcludedLanguage] | None = None
    includedSubtitles: list[ExcludedLanguage] | None = None
    requiredSubtitles: list[ExcludedLanguage] | None = None
    preferredSubtitles: list[ExcludedLanguage] | None = None
    excludedVisualTags: list[ExcludedVisualTag] | None = None
    includedVisualTags: list[ExcludedVisualTag] | None = None
    requiredVisualTags: list[ExcludedVisualTag] | None = None
    preferredVisualTags: list[ExcludedVisualTag] | None = None
    excludedAudioTags: list[ExcludedAudioTag] | None = None
    includedAudioTags: list[ExcludedAudioTag] | None = None
    requiredAudioTags: list[ExcludedAudioTag] | None = None
    preferredAudioTags: list[ExcludedAudioTag] | None = None
    excludedAudioChannels: list[ExcludedAudioChannel] | None = None
    includedAudioChannels: list[ExcludedAudioChannel] | None = None
    requiredAudioChannels: list[ExcludedAudioChannel] | None = None
    preferredAudioChannels: list[ExcludedAudioChannel] | None = None
    excludedStreamTypes: list[Type] | None = None
    includedStreamTypes: list[Type] | None = None
    requiredStreamTypes: list[Type] | None = None
    preferredStreamTypes: list[Type] | None = None
    excludedEncodes: list[ExcludedEncode] | None = None
    includedEncodes: list[ExcludedEncode] | None = None
    requiredEncodes: list[ExcludedEncode] | None = None
    preferredEncodes: list[ExcludedEncode] | None = None
    excludedRegexPatterns: list[ExcludedRegexPattern] | None = None
    includedRegexPatterns: list[IncludedRegexPattern] | None = None
    requiredRegexPatterns: list[RequiredRegexPattern] | None = None
    preferredRegexPatterns: list[PreferredRegexPattern] | None = None
    syncedPreferredRegexUrls: list[AnyUrl] | None = None
    syncedExcludedRegexUrls: list[AnyUrl] | None = None
    syncedIncludedRegexUrls: list[AnyUrl] | None = None
    syncedRequiredRegexUrls: list[AnyUrl] | None = None
    syncedRankedRegexUrls: list[AnyUrl] | None = None
    syncedPreferredStreamExpressionUrls: list[AnyUrl] | None = None
    syncedExcludedStreamExpressionUrls: list[AnyUrl] | None = None
    syncedIncludedStreamExpressionUrls: list[AnyUrl] | None = None
    syncedRequiredStreamExpressionUrls: list[AnyUrl] | None = None
    syncedRankedStreamExpressionUrls: list[AnyUrl] | None = None
    excludedReleaseGroups: list[ExcludedReleaseGroup] | None = None
    includedReleaseGroups: list[IncludedReleaseGroup] | None = None
    requiredReleaseGroups: list[RequiredReleaseGroup] | None = None
    preferredReleaseGroups: list[PreferredReleaseGroup] | None = None
    requiredKeywords: list[RequiredKeyword] | None = None
    includedKeywords: list[IncludedKeyword] | None = None
    excludedKeywords: list[ExcludedKeyword] | None = None
    preferredKeywords: list[PreferredKeyword] | None = None
    randomiseResults: bool | None = None
    enhanceResults: bool | None = None
    enhancePosters: bool | None = None
    excludeSeederRange: list[Any] | None = None
    includeSeederRange: list[Any] | None = None
    requiredSeederRange: list[Any] | None = None
    seederRangeTypes: list[SeederRangeType] | None = None
    excludeAgeRange: list[Any] | None = None
    includeAgeRange: list[Any] | None = None
    requiredAgeRange: list[Any] | None = None
    ageRangeTypes: list[AgeRangeType] | None = None
    digitalReleaseFilter: DigitalReleaseFilter | None = None
    enableSeadex: bool | None = None
    excludeSeasonPacks: bool | None = None
    excludeCached: bool | None = None
    excludeCachedFromAddons: list[ExcludeCachedFromAddon] | None = None
    excludeCachedFromServices: list[ExcludeCachedFromService] | None = None
    excludeCachedFromStreamTypes: list[Type] | None = None
    excludeCachedMode: ExcludeCachedMode | None = None
    excludeUncached: bool | None = None
    excludeUncachedFromAddons: list[ExcludeUncachedFromAddon] | None = None
    excludeUncachedFromServices: list[ExcludeUncachedFromService] | None = None
    excludeUncachedFromStreamTypes: list[Type] | None = None
    excludeUncachedMode: ExcludeCachedMode | None = None
    excludedStreamExpressions: list[ExcludedStreamExpression] | None = None
    requiredStreamExpressions: list[RequiredStreamExpression] | None = None
    preferredStreamExpressions: list[PreferredStreamExpression] | None = None
    includedStreamExpressions: list[IncludedStreamExpression] | None = None
    rankedStreamExpressions: list[RankedStreamExpression] | None = None
    rankedRegexPatterns: list[RankedRegexPattern] | None = None
    regexOverrides: list[RegexOverride] | None = None
    selOverrides: list[SelOverride] | None = None
    dynamicAddonFetching: DynamicAddonFetching | None = None
    groups: Groups | None = None
    sortCriteria: SortCriteria
    rpdbApiKey: str | None = None
    topPosterApiKey: str | None = None
    aioratingsApiKey: str | None = None
    aioratingsProfileId: str | None = None
    openposterdbApiKey: str | None = None
    openposterdbUrl: AnyUrl | None = None
    posterService: PosterService | None = None
    usePosterRedirectApi: bool | None = None
    usePosterServiceForMeta: bool | None = None
    formatter: Formatter2
    proxy: Proxy2 | None = None
    resultLimits: ResultLimits | None = None
    size: Size | None = None
    bitrate: Bitrate | None = None
    hideErrors: bool | None = None
    hideErrorsForResources: list[Name] | None = None
    statistics: Statistics | None = None
    tmdbAccessToken: str | None = None
    tmdbApiKey: str | None = None
    tvdbApiKey: str | None = None
    yearMatching: YearMatching | None = None
    titleMatching: TitleMatching | None = None
    seasonEpisodeMatching: SeasonEpisodeMatching | None = None
    deduplicator: Deduplicator | None = None
    autoPlay: AutoPlay | None = None
    areYouStillThere: AreYouStillThere | None = None
    precacheNextEpisode: bool | None = None
    alwaysPrecache: bool | None = None
    precacheCondition: str | None = Field(None, max_length=3000, min_length=1)
    precacheSelector: str | None = Field(None, max_length=3000, min_length=1)
    precacheSingleStream: bool | None = None
    preloadStreams: PreloadStreams | None = None
    services: list[Service5] | None = None
    presets: list[Preset3]
    addonCategoryColors: dict[str, str] | None = None
    catalogModifications: list[CatalogModification] | None = None
    mergedCatalogs: list[MergedCatalog] | None = None
    externalDownloads: bool | None = None
    cacheAndPlay: CacheAndPlay | None = None
    autoRemoveDownloads: bool | None = None
    checkOwned: bool
    nzbFailover: NzbFailover | None = None
    serviceWrap: ServiceWrap | None = None


class Metadata1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: Any
    name: str = Field(..., max_length=100, min_length=1)
    description: str = Field(..., max_length=1000, min_length=1)
    author: str = Field(..., max_length=20, min_length=1)
    source: Source9
    version: str = Field(..., pattern="^[0-9]+\\.[0-9]+\\.[0-9]+$")
    category: str = Field(..., max_length=20, min_length=1)
    services: list[Id] | None = None
    serviceRequired: bool | None = None
    setToSaveInstallMenu: bool
    sourceUrl: AnyUrl | None = None
    inputs: list[Any] | None = None
    changelog: list[ChangelogItem] | None = None
    changelogUrl: AnyUrl | None = None


class TemplateSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    metadata: Metadata1
    config: Any


class AIOStreamsSchemas(BaseModel):
    AIOStream_1: AIOStream | None = Field(None, alias="AIOStream")
    AIOratingsIsValidResponse_1: AIOratingsIsValidResponse | None = Field(
        None, alias="AIOratingsIsValidResponse"
    )
    AddonCatalogResponseSchema_1: AddonCatalogResponseSchema | None = Field(
        None, alias="AddonCatalogResponseSchema"
    )
    AddonCatalogSchema_1: AddonCatalogSchema | None = Field(None, alias="AddonCatalogSchema")
    CacheAndPlaySchema_1: CacheAndPlaySchema | None = Field(None, alias="CacheAndPlaySchema")
    CatalogResponseSchema_1: CatalogResponseSchema | None = Field(
        None, alias="CatalogResponseSchema"
    )
    ExtrasSchema_1: ExtrasSchema | None = Field(None, alias="ExtrasSchema")
    ManifestSchema_1: ManifestSchema | None = Field(None, alias="ManifestSchema")
    MetaPreviewSchema_1: MetaPreviewSchema | None = Field(None, alias="MetaPreviewSchema")
    MetaResponseSchema_1: MetaResponseSchema | None = Field(None, alias="MetaResponseSchema")
    MetaSchema_1: MetaSchema | None = Field(None, alias="MetaSchema")
    NNTPServersSchema: list[NNTPServersSchemaItem] | None = None
    OpenPosterDBIsValidResponse_1: OpenPosterDBIsValidResponse | None = Field(
        None, alias="OpenPosterDBIsValidResponse"
    )
    ParentConfigSchema_1: ParentConfigSchema | None = Field(None, alias="ParentConfigSchema")
    ParsedFileSchema_1: ParsedFileSchema | None = Field(None, alias="ParsedFileSchema")
    ParsedMetaSchema_1: ParsedMetaSchema | None = Field(None, alias="ParsedMetaSchema")
    ParsedStreamSchema_1: ParsedStreamSchema | None = Field(None, alias="ParsedStreamSchema")
    ParsedStreams: list[ParsedStream] | None = None
    RPDBIsValidResponse_1: RPDBIsValidResponse | None = Field(None, alias="RPDBIsValidResponse")
    SourceSchema_1: SourceSchema | None = Field(None, alias="SourceSchema")
    StreamResponseSchema_1: StreamResponseSchema | None = Field(None, alias="StreamResponseSchema")
    StreamSchema_1: StreamSchema | None = Field(None, alias="StreamSchema")
    SubtitleResponseSchema_1: SubtitleResponseSchema | None = Field(
        None, alias="SubtitleResponseSchema"
    )
    SubtitleSchema_1: SubtitleSchema | None = Field(None, alias="SubtitleSchema")
    TemplateSchema_1: TemplateSchema | None = Field(None, alias="TemplateSchema")
    TopPosterIsValidResponse_1: TopPosterIsValidResponse | None = Field(
        None, alias="TopPosterIsValidResponse"
    )
    UserDataSchema_1: UserDataSchema | None = Field(None, alias="UserDataSchema")
