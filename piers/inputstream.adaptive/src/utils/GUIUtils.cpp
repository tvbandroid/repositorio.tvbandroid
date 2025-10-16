/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "GUIUtils.h"

#include "StringUtils.h"

#ifdef INPUTSTREAM_TEST_BUILD
#include "test/KodiStubs.h"
#else
#include <kodi/gui/dialogs/OK.h>
#include <kodi/gui/dialogs/Select.h>
#include <kodi/gui/General.h>
#endif

using namespace UTILS;

int UTILS::GUI::SelectDialog(const std::string& windowTitle,
                             const std::vector<std::string>& entries,
                             int selectedIndex /* = DIALOG_NO_VALUE */,
                             unsigned int autocloseMs /* = 0 */)
{
  if (selectedIndex == DIALOG_NO_VALUE)
    selectedIndex = -1;

  const int ret = kodi::gui::dialogs::Select::Show(windowTitle, entries, selectedIndex, autocloseMs);
  if (ret == -1)
    return DIALOG_NO_VALUE;

  return ret;
}

std::string UTILS::GUI::GetLocalizedString(uint32_t labelId)
{
  return kodi::addon::GetLocalizedString(labelId);
}

void UTILS::GUI::MessageDialog(const std::string& windowTitle, const std::string& msg)
{
  kodi::gui::dialogs::OK::ShowAndGetInput(windowTitle, msg);
}

void UTILS::GUI::ErrorDialog(const std::string& errorMsg /* = "" */)
{
  const std::string msg = STRING::ReplacePlaceholders(GetLocalizedString(30301),
                                                      {{"error-details", errorMsg}}, '{', '}');

  kodi::gui::dialogs::OK::ShowAndGetInput(GetLocalizedString(30300), msg);
}

bool UTILS::GUI::IsAdjustRefreshRateEnabled()
{
  AdjustRefreshRateStatus adjRefreshRate{kodi::gui::GetAdjustRefreshRateStatus()};

  return (adjRefreshRate == AdjustRefreshRateStatus::ADJUST_REFRESHRATE_STATUS_ON_START ||
          adjRefreshRate == AdjustRefreshRateStatus::ADJUST_REFRESHRATE_STATUS_ON_STARTSTOP);
}
