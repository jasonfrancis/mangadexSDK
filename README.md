# mangadexSDK
This library makes it easy to fetch data from [Mangadex V5 API](https://api.mangadex.org).  You can generate a request to the API, run the request, and the results will be deserialized as Python classes.

## Examples
### Anonymous End Points
Many end points can be reached without any authorization.  The most basic example would be searching for a manga by its title.
```python
from mangadexSdk import MangadexSdk, RequestTypes, ResponseTypes

# Search manga end point
mangaListReq = RequestTypes.MangaList(title="mangadex bochi")
mangaList = mangaListReq.get()
print("Results:")
for manga in mangaList.results:
	print(f"Title: {manga.data.attributes.title}, Id: {manga.data.id}")
```
```
Results:
Title: {'en': 'Bocchi-sensei! Teach me MangaDex!'}, Id: d1c0d3f9-f359-467c-8474-0b2ea8e06f3d
```

Get the chapters for a manga
```python
# Get the feed for a given manga by Id
mangaFeedReq = RequestTypes.MangaFeed("d1c0d3f9-f359-467c-8474-0b2ea8e06f3d")
mangaFeed = mangaFeedReq.get()
for chapter in mangaFeed.results:
	print(f"Title: {chapter.data.attributes.title} Id: {chapter.data.id}")
```
```
Title: Site Theme, Chapter Language, Site Language Id: 0463105e-327e-4885-a6de-bf4b359bd0d8
Title: MDList (2), Classificar Id: 1531a0ba-5ce0-4af0-b5fa-b6581dfe9780
Title: Reportar un Comentario, Habilitar a Autenticaci&oacute;n de Dous Factores (Galego) Id: 1a1e7780-9973-4174-88b3-01dca71c65a0
Title: Reportar (1), Reportar (2) (Galego) Id: 2fef7d04-958a-45aa-b361-d164f0cfea27
...
Title: Dodawanie nowej grupy, Dodawanie nowej mangi Id: ea0e267f-58f3-4e5c-9283-504d2d383bf5
Title: Śledzenie mangi (3), MDList (1) Id: ea3c0fad-887b-4ce1-9484-69aa83fc2751

```

Get a single chapter, and then get the URLs for page images.
```python
# Get a chapter by id
chapterReq = RequestTypes.ChapterRequest("0463105e-327e-4885-a6de-bf4b359bd0d8")
chapter = chapterReq.get()
print(f"Chapter Title: {chapter.data.attributes.title}")

# Get an AtHomeServer for the chapter
atHomeServerReq = RequestTypes.AtHomeServer(chapter.data.id)
print(f"Fetching {atHomeServerReq.getPath()}")
atHomeServer = atHomeServerReq.get()

# Get the page image URLs for the chapter.
pageUrls = chapter.data.getPageUrls(atHomeServer)
print("Pages:")
for page in pageUrls["data"]:
	print(page)

```
```
Chapter Title: Site Theme, Chapter Language, Site Language
Fetching at-home/server/0463105e-327e-4885-a6de-bf4b359bd0d8
Pages:
https://{an AtHome Server}:{port}}/{temporary key}/data/{chapter's hash}/c1-bdb912bcd8692a937670413b6920670b739a16049b6f0715bda1e5dce91bef7e.png
```

### End Points Requiring Authorization
End Points that require authorization require an additional step of creating an instance of the `MangaDexSdk` class.  The first time you create a new `MangaDexSdk` you will be prompted for your username and password. These credentials will be securely stored using the [Keyring](https://pypi.org/project/keyring/) library.

A good example would be fetching your feed of latest chapters.
```python
api = MangadexSdk()
# Get the logged in user's MangaFeed.
userFeedReq = RequestTypes.UserFollowsMangaFeed()
userFeed = userFeedReq.get(api)
print (f"Got {len(userFeed.results)} of {userFeed.total} chapters.")
```
```
settings.json does not exist
Enter your MangaDex username: jdoe
Saving username "jdoe" to settings.json ...
Done.
Writing updated token to settings
Got 100 of 1001 chapters.
```
If you need to change your stored username or password you can run your script with the `--update-username` or `--update-password` flags. Or you can directly invoke the `mangaDex.Settings.setUsername()` and `MangaDexSdk.deletePassword()` methods.