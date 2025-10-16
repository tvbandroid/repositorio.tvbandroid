/*
 *  Copyright (C) 2024 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include <string>

#include <nlohmann/json.hpp>

namespace UTILS
{
namespace JSON
{

/*!
 * \brief Get a JSON value from a path by using JSON pointer (RFC 6901)
 *        e.g. "/a/b/c"
 * \param node The json object where get the value
 * \param path The JSON pointer path where the value is contained
 * \return The json object if found, otherwise nullptr.
 */
const nlohmann::json* GetValueAtPath(const nlohmann::json& node, std::string path);

/*!
 * \brief Get value from an unknown JSON path,
 *        then traverse all even nested dictionaries to search for the specified key name.
 * \param node The json object where find the path/value
 * \param keyName The key name to search for
 * \return The json object if found, otherwise nullptr.
 */
const nlohmann::json* GetValueTraversePaths(const nlohmann::json& node, const std::string& keyName);

} // namespace JSON
} // namespace UTILS
