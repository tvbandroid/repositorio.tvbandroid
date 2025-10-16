/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

namespace CDM_DBG
{
enum class LogLevel
{
  DEBUG,
  INFO,
  WARNING,
  ERROR,
  FATAL
};

void Log(const LogLevel level, const char* format, ...);

void SetDBGMsgCallback(void (*msgcb)(const LogLevel level, const char* msg));

} // namespace cdm
