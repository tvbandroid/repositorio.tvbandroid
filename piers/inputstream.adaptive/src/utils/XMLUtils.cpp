/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "XMLUtils.h"

#include "oscompat.h" // _mkgmtime
#include "StringUtils.h"
#include "log.h"
#include "pugixml.hpp"

#include <cstdio> // sscanf
#include <regex>

using namespace UTILS::XML;
using namespace pugi;

namespace
{
const pugi::xml_node TraverseTags(const pugi::xml_node node, const std::string& tagName)
{
  if (node.name() == tagName)
  {
    return node;
  }

  // Recursively search the child nodes
  for (pugi::xml_node child = node.first_child(); child; child = child.next_sibling())
  {
    const pugi::xml_node found_node = TraverseTags(child, tagName);
    if (found_node)
    {
      return found_node;
    }
  }

  // Tag not found
  return pugi::xml_node();
}
} // unnamed namespace

double UTILS::XML::ParseDate(const char* timeStr,
                             double fallback /* = std::numeric_limits<double>::max() */)
{
  int year, mon, day, hour, minu;
  double sec;

  // This code dont take in account of timezone
  if (std::sscanf(timeStr, "%d-%d-%dT%d:%d:%lf", &year, &mon, &day, &hour, &minu, &sec) == 6)
  {
    tm tmd{0};
    tmd.tm_year = year - 1900;
    tmd.tm_mon = mon - 1;
    tmd.tm_mday = day;
    tmd.tm_hour = hour;
    tmd.tm_min = minu;
    tmd.tm_sec = 0;
    return static_cast<double>(_mkgmtime(&tmd)) + sec;
  }

  return fallback;
}

double UTILS::XML::ParseDuration(std::string_view durationStr)
{
  static const std::regex pattern("^P(?:([0-9]*)Y)?(?:([0-9]*)M)?(?:([0-9]*)D)"
                                  "?(?:T(?:([0-9]*)H)?(?:([0-9]*)M)?(?:([0-9.]*)S)?)?$");

  if (durationStr.empty())
    return 0;

  std::match_results<std::string_view::const_iterator> matches;
  std::regex_match(durationStr.cbegin(), durationStr.cend(), matches, pattern);

  if (matches.size() == 0)
  {
    LOG::LogF(LOGWARNING, "Duration string \"%s\" is not valid.", durationStr);
    return 0;
  }

  double years = STRING::ToDouble(matches[1].str());
  double months = STRING::ToDouble(matches[2].str());
  double days = STRING::ToDouble(matches[3].str());
  double hours = STRING::ToDouble(matches[4].str());
  double minutes = STRING::ToDouble(matches[5].str());
  double seconds = STRING::ToDouble(matches[6].str());

  // Assume a year always has 365 days and a month always has 30 days.
  return years * (60 * 60 * 24 * 365) + months * (60 * 60 * 24 * 30) + days * (60 * 60 * 24) +
         hours * (60 * 60) + minutes * 60 + seconds;
}

size_t UTILS::XML::CountChilds(pugi::xml_node node, const char* childTagName /* = "" */)
{
  size_t count{0};
  for ([[maybe_unused]] xml_node nodeChild : node.children(childTagName))
  {
    count++;
  }
  return count;
}

xml_attribute UTILS::XML::FirstAttributeNoPrefix(pugi::xml_node node,
                                                 std::string_view attributeName)
{
  for (xml_attribute attr : node.attributes())
  {
    std::string_view currentAttribName = attr.name();
    size_t delimiterPos = currentAttribName.find(':');
    if (delimiterPos == std::string::npos)
      continue;

    currentAttribName.remove_prefix(delimiterPos + 1);
    if (currentAttribName != attributeName)
      continue;

    return attr;
  }

  return xml_attribute();
}

std::string_view UTILS::XML::GetAttrib(pugi::xml_node& node,
                                       const char* name,
                                       const char* defaultValue /* = "" */)
{
  return node.attribute(name).as_string(defaultValue);
}

int UTILS::XML::GetAttribInt(pugi::xml_node& node, const char* name, int defaultValue /* = 0 */)
{
  return node.attribute(name).as_int(defaultValue);
}

uint32_t UTILS::XML::GetAttribUint32(pugi::xml_node& node,
                                     const char* name,
                                     uint32_t defaultValue /* = 0 */)
{
  return node.attribute(name).as_uint(defaultValue);
}

uint64_t UTILS::XML::GetAttribUint64(pugi::xml_node& node, const char* name, uint64_t defaultValue)
{
  return node.attribute(name).as_ullong(defaultValue);
}

bool UTILS::XML::QueryAttrib(pugi::xml_node& node, const char* name, std::string& value)
{
  xml_attribute attrib = node.attribute(name);
  if (attrib)
  {
    value = attrib.as_string();
    return true;
  }
  return false;
}

bool UTILS::XML::QueryAttrib(pugi::xml_node& node, const char* name, int& value)
{
  xml_attribute attrib = node.attribute(name);
  if (attrib)
  {
    value = attrib.as_int();
    return true;
  }
  return false;
}

bool UTILS::XML::QueryAttrib(pugi::xml_node& node, const char* name, uint32_t& value)
{
  xml_attribute attrib = node.attribute(name);
  if (attrib)
  {
    value = attrib.as_uint();
    return true;
  }
  return false;
}

bool UTILS::XML::QueryAttrib(pugi::xml_node& node, const char* name, uint64_t& value)
{
  xml_attribute attrib = node.attribute(name);
  if (attrib)
  {
    value = attrib.as_ullong();
    return true;
  }
  return false;
}

const pugi::xml_node UTILS::XML::GetNodeTraverseTags(pugi::xml_node node, const std::string& tagName)
{
  return TraverseTags(node, tagName);
}
