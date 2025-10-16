/*
 *  Copyright (C) 2024 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "JsonUtils.h"

#include "log.h"

using njson = nlohmann::json;

namespace
{
const nlohmann::json* TraversePaths(const nlohmann::json& node, const std::string& keyName)
{
  if (node.is_object())
  {
    for (auto& [jName, jValue] : node.items())
    {
      if (jName == keyName)
      {
        if (jValue.is_string() || jValue.is_number())
          return &jValue;
        else if (jValue.is_object() || jValue.is_array())
        {
          const njson* ret = TraversePaths(jValue, keyName);
          if (ret)
            return ret;
        }
      }
      else if (jValue.is_array())
      {
        for (const auto& item : jValue)
        {
          const njson* ret = TraversePaths(item, keyName);
          if (ret)
            return ret;
        }
      }
      else if (jValue.is_object())
      {
        const njson* ret = TraversePaths(jValue, keyName);
        if (ret)
          return ret;
      }
    }
  }
  else if (node.is_array())
  {
    for (const auto& item : node)
    {
      const njson* ret = TraversePaths(item, keyName);
      if (ret)
        return ret;
    }
  }

  return nullptr;
}

} // unnamed namespace

const nlohmann::json* UTILS::JSON::GetValueAtPath(const nlohmann::json& node, std::string path)
{
  if (path.empty())
    return nullptr;

  if (path.front() != '/')
    path.insert(0, "/");

  try
  {
    const njson::json_pointer jPointer(path);

    if (node.contains(jPointer))
      return &node.at(jPointer);
  }
  catch (...)
  {
    LOG::LogF(LOGERROR, "Cannot get JSON data, possible malformed path \"%s\"", path.c_str());
  }

  return nullptr;
}

const nlohmann::json* UTILS::JSON::GetValueTraversePaths(const nlohmann::json& node,
                                                         const std::string& keyName)
{
  return TraversePaths(node, keyName);
}
