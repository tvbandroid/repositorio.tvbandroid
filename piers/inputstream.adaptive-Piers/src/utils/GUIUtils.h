/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace UTILS
{
namespace GUI
{
constexpr int DIALOG_NO_VALUE = -1;

/*!
 * \brief Show a select dialog window
 * \param windowTitle The title of the window.
 * \param entries List about entries.
 * \param selectedIndex Preselected entry based on index (default DIALOG_NO_VALUE select the first entry).
 * \param autocloseSecs To close dialog automatic after the given MS time (default 0 it stays open).
 * \return The selected entry index, otherwise DIALOG_NO_VALUE when nothing selected or canceled.
 */
int SelectDialog(const std::string& windowTitle,
                 const std::vector<std::string>& entries,
                 int selectedIndex = DIALOG_NO_VALUE,
                 unsigned int autocloseMs = 0);

/*!
 * \brief Get add-on localized unicode string from strings included on
 *        "./resources/language/resource.language.??_??/strings.po" or Kodi core.
 * \param labelId The label ID of the string to be retrieved.
 * \param entries List about entries.
 * \return The localized string.
 */
std::string GetLocalizedString(uint32_t labelId);

/*!
 * \brief Show a message dialog window
 * \param windowTitle The title of the window.
 * \param msg The text message.
 */
void MessageDialog(const std::string& windowTitle, const std::string& msg);

/*!
 * \brief Show an error message dialog window that show a message with
 *        "Unable to play the stream" followed by the specified error message details.
 * \param errorMsg[OPT] The error details, can be empty.
 */
void ErrorDialog(const std::string& errorMsg = "");

/*!
 * \brief Check if "Adjust refresh rate" kodi setting is enabled
 * \return true if enabled, otherwise false
 */
bool IsAdjustRefreshRateEnabled();

} // namespace GUI
} // namespace UTILS
