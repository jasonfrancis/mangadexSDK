from enum import Enum
from requests.models import Response
from typing import List
from datetime import datetime
from .mangaDex import MangaDexSdk
from .responseTypes import AtHomeServer, AuthorListResult, AuthorResult, ChapterResult, FeedResult, MangaListResult, MangaResult

class OrderValue(Enum):
	asc = 1
	desc = 2
class Order:
	def __init__(self, volume:OrderValue = OrderValue.asc, chapter:OrderValue = OrderValue.desc):
		self.volume = volume
		self.chapter = chapter
class ChapterOrder:
	def __init__(self, createdAt:OrderValue=None, updatedAt:OrderValue=None, publishAt:OrderValue=None, volume:OrderValue=None, chapter:OrderValue=None):
		self.createdAt = createdAt
		self.updatedAt = updatedAt
		self.publishAt = publishAt
		self.volume = volume
		self.chapter = chapter
	def toQueryString(self, prependAmpersand:bool=True):
		params = []
		result = "&" if prependAmpersand else ""

		if(self.createdAt): params.append(f"order[createdAt]={self.createdAt.name}")
		if(self.updatedAt): params.append(f"order[updatedAt]={self.updatedAt.name}")
		if(self.publishAt): params.append(f"order[publishAt]={self.publishAt.name}")
		if(self.volume): params.append(f"order[volume]={self.volume.name}")
		if(self.chapter): params.append(f"order[chapter]={self.chapter.name}")
		
		return result + "&".join(params)

class AndOr(Enum):
	AND = 1
	OR = 2

class BaseRequest:
	@staticmethod
	def formatDatetime(dt:datetime) -> str:
		#YYYY-MM-DDTHH:MM:S
		return dt.strftime("%Y-%m-%dT%H:%M:%S")
	@staticmethod
	def queryArrayOfStrings(input:List[str], paramName:str, prependAmpersand:bool=True):
		result = "&" if prependAmpersand else ""
		paramName = paramName if paramName.endswith("[]") else f"{paramName}[]"
		params = []
		for val in input : params.append(f"{paramName}={val}")
		return result + "&".join(params)
class RequestTypes:
	class MangaRequest:
		def __init__(self, mangaId:str):
			self.mangaId = mangaId
			self._get = lambda : MangaDexSdk.get(self.getPath())
			self.get = lambda : MangaResult.fromJson(self._get().text)
		def getPath(self) -> str:
			return f"manga/{self.mangaId}"
	class MangaList:
		def __init__(self, limit:int=10, offset:int=0, title:str=None, authors:List[str]=None, artists:List[str]=None,
					year:int=None, includedTags:List[str]=None, includedTagsMode:AndOr=AndOr.AND, excludedTags:List[str]=None,
					excludedTagsMode:AndOr=AndOr.OR, status:List[str]=None, originalLanguage:List[str]=None,
					publicationDemographic:List[str]=None, ids:List[str]=None, contentRating:List[str]=None, createdAtSince:datetime=None,
					updatedAtSince:datetime=None, order:Order=None):
			if limit < 1 or limit > 100:
				raise Exception("limit must be an integer between 1 and 100.")
			self.limit = limit
			if offset < 0:
				raise Exception("Offset must be 0 or greater.")
			self.offset = offset
			self.title = title
			self.authors = authors
			self.artists = artists
			self.year = year
			self.includedTags = includedTags
			self.includedTagsMode = includedTagsMode
			self.excludedTags = excludedTags
			self.excludedTagsMode = excludedTagsMode
			self.status = status
			self.originalLanguage = originalLanguage
			self.publicationDemographic = publicationDemographic
			if ids and len(ids) > 100:
				raise Exception(f"The array of ids to filter by may not be more than 100 items.")
			self.ids= ids
			self.contentRating = contentRating
			self.createdAtSince = createdAtSince
			self.updatedAtSince = updatedAtSince
			self.order = order

			self._get:Response = lambda : MangaDexSdk.get(self.getPath())
			self.get = lambda : MangaListResult.fromJson(self._get().text)
		def getPath(self) -> str:
			output = f"manga?limit={self.limit}&offset={self.offset}"
			output += "" if not self.title else f"&title={self.title}"
			output += "" if not self.authors else BaseRequest.queryArrayOfStrings(self.authors, "authors")
			output += "" if not self.artists else BaseRequest.queryArrayOfStrings(self.artists, "artists")
			output += "" if not self.year else f"&year={self.year}"
			output += "" if not self.includedTags or not self.includedTagsMode else BaseRequest.queryArrayOfStrings(self.includedTags, "includedTags")
			output += "" if not self.includedTags or not self.includedTagsMode else f"&includedTagsMode={self.includedTagsMode}"
			output += "" if not self.excludedTags or not self.excludedTagsMode else BaseRequest.queryArrayOfStrings(self.excludedTags, "excludedTags")
			output += "" if not self.excludedTags or not self.excludedTagsMode else f"&excludedTagsMode={self.excludedTagsMode}"
			output += "" if not self.status else BaseRequest.queryArrayOfStrings(self.status, "status")
			output += "" if not self.originalLanguage else BaseRequest.queryArrayOfStrings(self.originalLanguage, "originalLanguage")
			output += "" if not self.publicationDemographic else BaseRequest.queryArrayOfStrings(self.publicationDemographic, "publicationDemographic")
			output += "" if not self.ids else BaseRequest.queryArrayOfStrings(self.ids, "ids")
			output += "" if not self.contentRating else BaseRequest.queryArrayOfStrings(self.contentRating, "contentRating")
			output += "" if not self.createdAtSince else f"&createdAtSince={BaseRequest.formatDatetime(self.createdAtSince)}"
			output += "" if not self.updatedAtSince else f"&updatedAtSince={BaseRequest.formatDatetime(self.updatedAtSince)}"
			# the documentation is too vague about what this string should look like
			# output += "" if not self.order else f"&order={json.dumps(self.order)}"
			return output
	
	class ChapterRequest:
		def __init__(self, chapterId:str):
			self.chapterId = chapterId
			self._get = lambda : MangaDexSdk.get(self.getPath())
			self.get = lambda : ChapterResult.fromJson(self._get().text)
		def getPath(self) -> str:
			return f"chapter/{self.chapterId}"

	class ChapterList:
		def __init__(self, limit:int=10, offset:int=0, title:str=None, groups:List[str]=None, uploader:str=None,
					manga:str=None, volume:str=None, chapter:str=None, translatedLanguage:str=None,
					createdAtSince:datetime=None, updatedAtSince:datetime=None, publishAtSince:datetime=None,
					order:ChapterOrder=None):
			if limit < 1 or limit > 100:
				raise Exception("limit must be an integer between 1 and 100.")
			self.limit = limit
			if offset < 0:
				raise Exception("Offset must be 0 or greater.")
			self.limit = limit
			self.offset = offset
			self.title = title
			self.groups = groups
			self.uploader = uploader
			self.manga = manga
			self.volume = volume
			self.chapter = chapter
			self.translatedLanguage = translatedLanguage
			self.createdAtSince = createdAtSince
			self.updatedAtSince = updatedAtSince
			self.publishAtSince = publishAtSince
			self.order = order

			self._get:Response = lambda : MangaDexSdk.get(self.getPath())
			self.get = lambda : FeedResult.fromJson(self._get().text)
		def getPath(self):
			output = f"chapter?limit={self.limit}&offset={self.offset}"
			output += "" if not self.title else f"&title={self.title}"
			output += "" if not self.groups else BaseRequest.queryArrayOfStrings(self.groups, "groups")
			output += "" if not self.uploader else f"&uploader={self.uploader}"
			output += "" if not self.manga else f"&manga={self.manga}"
			output += "" if not self.volume else f"&volumne={self.volume}"
			output += "" if not self.chapter else f"&chapter={self.chapter}"
			output += "" if not self.translatedLanguage else f"&translatedLanguage={self.translatedLanguage}"
			output += "" if not self.createdAtSince else f"&createdAtSince={BaseRequest.formatDatetime(self.createdAtSince)}"
			output += "" if not self.updatedAtSince else f"&updatedAtSince={BaseRequest.formatDatetime(self.updatedAtSince)}"
			output += "" if not self.publishAtSince else f"&publishAtSince={BaseRequest.formatDatetime(self.publishAtSince)}"
			# the documentation is too vague about what this string should look like
			# output += "" if not self.order else f"&order={json.dumps(self.order)}"
			return output
	
	class AuthorRequest:
		def __init__(self, authorId:str):
			self.authorId = authorId
			self._get = lambda : MangaDexSdk.get(self.getPath())
			self.get = lambda : AuthorResult.fromJson(self._get().text)
		def getPath(self) -> str:
			return f"author/{self.authorId}"

	class AuthorList:
		def __init__(self, limit:int=10, offset:int=0, ids:List[str]=None, name:str=None):
			if limit < 1 or limit > 100:
				raise Exception("limit must be an integer between 1 and 100.")
			if offset < 0:
				raise Exception("Offset must be 0 or greater.")
			if ids and len(ids) > 100:
				raise Exception(f"The array of ids to filter by may not be more than 100 items.")
			self.limit = limit
			self.offset = offset
			self.ids = ids
			self.name = name

			self._get:Response = lambda : MangaDexSdk.get(self.getPath())
			self.get = lambda : AuthorListResult.fromJson(self._get().text)
		def getPath(self) -> str:
			output = f"author?limit={self.limit}&offset={self.offset}"
			output += "" if not self.ids else BaseRequest.queryArrayOfStrings(self.ids, "ids")
			output += "" if not self.name else f"&name={self.name}"
			return output

	class FeedRequest:
		def __init__(self, path:str, limit:int = None, offset:int = None, locales:List[str] = None,
					createdAtSince:datetime = None, updatedAtSince:datetime = None, publishAtSince:datetime = None,
					order:ChapterOrder = None):
			limit = 100 if limit == None else limit
			if(limit < 1 or limit > 500):
				raise Exception(f"FeedRequest limit must be between 1 and 500. {limit} provided.")
			if(offset != None and offset < 0):
				raise Exception(f"FeedRequest offset, if provided, must be a positive integer. {offset} provided")
			self.path = path
			self.limit = limit
			self.offset = offset
			self.locales = locales
			self.createdAtSince = createdAtSince
			self.updatedAtSince = updatedAtSince
			self.publishAtSince = publishAtSince
			self.order = order

			self._get:Response = lambda : MangaDexSdk.get(self.getPath())
			self.get:FeedResult = lambda : FeedResult.fromJson(self._get().text)
		def getPath(self) -> str:
			output = f"{self.path}?limit={self.limit}"
			output += "" if not self.offset else f"&offset={self.offset}"
			output += "" if not self.locales else BaseRequest.queryArrayOfStrings(self.locales, "translatedLanguage")
			output += "" if not self.createdAtSince else f"&createdAtSince={BaseRequest.formatDatetime(self.createdAtSince)}"
			output += "" if not self.updatedAtSince else f"&updatedAtSince={BaseRequest.formatDatetime(self.updatedAtSince)}"
			output += "" if not self.publishAtSince else f"&publishAtSince={BaseRequest.formatDatetime(self.publishAtSince)}"
			output += "" if not self.order else self.order.toQueryString()
			
			return output

	class UserFollowsMangaFeed(FeedRequest):
		def __init__(self, limit:int=None, offset:int=None, locales:List[str]=None, createdAtSince:datetime=None, updatedAtSince:datetime=None, publishAtSince:datetime=None, order:ChapterOrder=None):
			super().__init__("user/follows/manga/feed", limit=limit, offset=offset, locales=locales, createdAtSince=createdAtSince, updatedAtSince=updatedAtSince, publishAtSince=publishAtSince, order=order)
			# User follows cannot use the anonymous get.
			del self.get
			del self._get
		def _get(self, api:MangaDexSdk) -> Response:
			return api.getAuthenticated(self.getPath())
		def get(self, api:MangaDexSdk) -> FeedResult:
			return FeedResult.fromJson(self._get(api).text)
	class MangaFeed(FeedRequest):
		def __init__(self, mangaId:str, limit:int=None, offset:int=None, locales:List[str]=None, createdAtSince:datetime=None, updatedAtSince:datetime=None, publishAtSince:datetime=None, order:ChapterOrder=None):
			super().__init__(f"manga/{mangaId}/feed", limit=limit, offset=offset, locales=locales, createdAtSince=createdAtSince, updatedAtSince=updatedAtSince, publishAtSince=publishAtSince, order=order)
	class ListFeed(FeedRequest):
		def __init__(self, listId:str, limit:int=None, offset:int=None, locales:List[str]=None, createdAtSince:datetime=None, updatedAtSince:datetime=None, publishAtSince:datetime=None, order:ChapterOrder=None):
			super().__init__(f"list/{listId}/feed", limit=limit, offset=offset, locales=locales, createdAtSince=createdAtSince, updatedAtSince=updatedAtSince, publishAtSince=publishAtSince, order=order)

	class AtHomeServer:
		def __init__(self, chapterId:str, forcePort443:bool=False):
			self.chapterId = chapterId
			self.forcePort443 = forcePort443
			self._get = lambda : MangaDexSdk.get(self.getPath())
		def get(self):
			result = AtHomeServer.fromJson(self._get().text)
			result.setChapterId(self.chapterId)
			return result
		def getPath(self) -> str:
			output = f"at-home/server/{self.chapterId}"
			output += "" if not self.forcePort443 else "?forcePort443=true"
			return output