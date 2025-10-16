/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "debug.h"

#include <cstdarg>
#include <cstdio>

#ifdef _MSC_VER
#define snprintf _snprintf
#endif

struct dbgContext
{
  const char* name;
  void (*msgCallback)(const CDM_DBG::LogLevel level, const char* msg);
};

dbgContext debugContext = {"WV-CDM-Library", nullptr};

void CDM_DBG::Log(const CDM_DBG::LogLevel level, const char* format, ...)
{
  if (!debugContext.msgCallback)
    return;

  char msg[2048];
  const int len = snprintf(msg, sizeof(msg), "[%s] ", debugContext.name);
  if (len < 0 || len >= sizeof(msg))
  {
    debugContext.msgCallback(CDM_DBG::LogLevel::ERROR,
                             "Cannot print log string: Context name too long");
    return;
  }

  va_list ap;
  va_start(ap, format);
  const int formattedLen = vsnprintf(msg + len, sizeof(msg) - len, format, ap);
  va_end(ap);
  if (formattedLen < 0 || formattedLen >= (sizeof(msg) - len))
  {
    debugContext.msgCallback(CDM_DBG::LogLevel::ERROR,
                             "Cannot print log string: Text content too long");
    return;
  }

  debugContext.msgCallback(level, msg);
}

void CDM_DBG::SetDBGMsgCallback(void (*msgcb)(const CDM_DBG::LogLevel level, const char* msg))
{
  debugContext.msgCallback = msgcb;
}
