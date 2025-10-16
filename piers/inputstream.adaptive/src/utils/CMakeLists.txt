set(SOURCES
  Base64Utils.cpp
  CharArrayParser.cpp
  CurlUtils.cpp
  DigestMD5Utils.cpp
  FileUtils.cpp
  GUIUtils.cpp
  JsonUtils.cpp
  oscompat.cpp
  StringUtils.cpp
  ThreadPool.cpp
  UrlUtils.cpp
  Utils.cpp
  XMLUtils.cpp
)

set(HEADERS
  Base64Utils.h
  CharArrayParser.h
  CryptoUtils.h
  CurlUtils.h
  DigestMD5Utils.h
  FileUtils.h
  GUIUtils.h
  JsonUtils.h
  log.h
  oscompat.h
  ResultType.h
  StringUtils.h
  ThreadPool.h
  UrlUtils.h
  Utils.h
  XMLUtils.h
)

add_dir_sources(SOURCES HEADERS)
