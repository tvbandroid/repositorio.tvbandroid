/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "TTML.h"

#include "pugixml.hpp"
#include "utils/StringUtils.h"
#include "utils/XMLUtils.h"
#include "utils/log.h"

#include <cstring>

using namespace pugi;
using namespace UTILS;

bool TTML2SRT::Parse(const void* buffer, size_t bufferSize, uint64_t timescale)
{
  m_currSubPos = 0;
  m_seekTime = NO_PTS;
  m_subtitlesList.clear();
  m_timescale = timescale;
  m_styles.clear();
  m_styleStack.resize(1); // Add empty style

  if (!ParseData(buffer, bufferSize))
    return false;

  return true;
}

bool TTML2SRT::TimeSeek(uint64_t seekPos)
{
  m_seekTime = seekPos;
  return true;
}

void TTML2SRT::Reset()
{
  m_subtitlesList.clear();
  m_currSubPos = 0;
  m_lastSubFeed = SubtitleData();
}

bool TTML2SRT::Prepare(uint64_t& pts, uint32_t& duration)
{
  // Feed Kodi subtitle decoder with one subtitle at a time

  if (m_isFile && m_seekTime != NO_PTS)
  {
    // For cases of single "sidecar" file's
    // there is stored whole file in memory, so its needed to find the position
    // of the first subtitle that fall into the seek time
    m_currSubPos = 0;
    while (m_currSubPos < m_subtitlesList.size() && m_subtitlesList[m_currSubPos].end < m_seekTime)
    {
      m_currSubPos++;
    }

    m_seekTime = NO_PTS;
  }

  if (m_currSubPos >= m_subtitlesList.size())
    return false;

  SubtitleData& sub = m_subtitlesList[m_currSubPos++];

  // Some segmented TTML repeat the last cue on the next segment packet(s)
  // this causes a doubling of the text displayed on the screen, so skip it
  if (sub.start == m_lastSubFeed.start && sub.end == m_lastSubFeed.end &&
      sub.text == m_lastSubFeed.text)
  {
    return false;
  }

  pts = sub.start;
  duration = static_cast<uint32_t>(sub.end - sub.start);

  m_preparedSubText = sub.text;
  m_lastSubFeed = sub;

  return true;
}

bool TTML2SRT::ParseData(const void* buffer, size_t bufferSize)
{
  xml_document doc;
  xml_parse_result parseRes = doc.load_buffer(buffer, bufferSize);

  if (parseRes.status != status_ok)
  {
    LOG::LogF(LOGERROR, "Failed to parse XML data, error code: %i", parseRes.status);
    return false;
  }

  xml_node nodeTT = doc.child("tt");
  if (!nodeTT)
  {
    LOG::LogF(LOGERROR, "Failed to get <tt> tag element.");
    return false;
  }

  m_tickRate = XML::GetAttribUint64(nodeTT, "ttp:tickRate");

  uint64_t frameRate;
  if (XML::QueryAttrib(nodeTT, "ttp:frameRate", frameRate))
  {
    m_frameRateNum = frameRate;
    m_frameRateDen = 1;
  }

  std::string frameRateMulStr;
  if (XML::QueryAttrib(nodeTT, "ttp:frameRateMultiplier", frameRateMulStr))
  {
    unsigned int num;
    unsigned int den;
    // Accepted formats: "n n" or "n\tn"
    if (sscanf(frameRateMulStr.c_str(), "%u%*[\t ]%u", &num, &den) == 2)
    {
      m_frameRateNum = num;
      m_frameRateDen = den;
    }
  }

  XML::QueryAttrib(nodeTT, "ttp:subFrameRate", m_subFrameRate);

  ParseTagHead(nodeTT);
  ParseTagBody(nodeTT);

  return true;
}

void TTML2SRT::ParseTagHead(pugi::xml_node nodeTT)
{
  xml_node nodeHead = nodeTT.child("head");
  if (!nodeHead)
    return;

  // Parse <styling> tag
  xml_node nodeStyling = nodeHead.child("styling");
  if (nodeStyling)
  {
    // Parse <styling> <style> child tags
    for (xml_node node : nodeStyling.children("style"))
    {
      InsertStyle(ParseStyle(node));
    }
  }
}

void TTML2SRT::ParseTagBody(pugi::xml_node nodeTT)
{
  xml_node nodeBody = nodeTT.child("body");
  if (!nodeBody)
    return;

  StackStyle(XML::GetAttrib(nodeBody, "style"));

  // Parse <body> <div> child tags
  for (xml_node nodeDiv : nodeBody.children("div"))
  {
    // Subtitles that make use of images to show text are not supported
    if (nodeDiv.attribute("smpte:backgroundImage") || nodeDiv.attribute("tts:backgroundImage"))
    {
      LOG::LogF(LOGWARNING,
                "The \"backgroundImage\" attribute to show subtitles images is not supported.");
    }

    // Parse <body> <div> <p> child tags
    for (xml_node nodeP : nodeDiv.children("p"))
    {
      std::string_view id = XML::GetAttrib(nodeP, "xml:id");
      std::string_view beginTime = XML::GetAttrib(nodeP, "begin");
      std::string_view endTime = XML::GetAttrib(nodeP, "end");

      StackStyle(XML::GetAttrib(nodeP, "style"));
      // Parse additional style attributes of node and add them as another style stack
      StackStyle(ParseStyle(nodeP));

      std::string subText;
      // NOTE: subtitle text is contained as children of the <p> tag as PCDATA type
      // so we treat the text as XML nodes
      for (pugi::xml_node subTextNode : nodeP.children())
      {
        if (subTextNode.type() == pugi::node_pcdata)
        {
          // It's a text part
          AppendStyledText(subTextNode.value(), subText);
        }
        else if (subTextNode.type() == pugi::node_element)
        {
          // It's a XML tag
          if (STRING::Compare(subTextNode.name(), "span"))
          {
            ParseTagSpan(subTextNode, subText);
          }
          else if (STRING::Compare(subTextNode.name(), "br"))
          {
            subText += "<br/>";
          }
        }
      }

      UnstackStyle();
      UnstackStyle();
      StackSubtitle(id, beginTime, endTime, subText);
    }
  }
}

void TTML2SRT::ParseTagSpan(pugi::xml_node spanNode, std::string& subText)
{
  StackStyle(XML::GetAttrib(spanNode, "style"));
  std::string_view beginTime = XML::GetAttrib(spanNode, "begin");
  std::string_view endTime = XML::GetAttrib(spanNode, "end");
  const bool hasTiming = !beginTime.empty() && !endTime.empty();
  std::string text;

  // Parse additional style attributes of node and add them as another style stack
  StackStyle(ParseStyle(spanNode));

  // Treats the data of the Span tag as PCDATA type, and so text as XML nodes
  for (pugi::xml_node spanTextNode : spanNode.children())
  {
    if (spanTextNode.type() == pugi::node_pcdata)
    {
      // It's a text part
      AppendStyledText(spanTextNode.value(), text);
    }
    else if (spanTextNode.type() == pugi::node_element)
    {
      if (STRING::Compare(spanTextNode.name(), "span"))
      {
        ParseTagSpan(spanTextNode, text);
      }
      else if (STRING::Compare(spanTextNode.name(), "br"))
      {
        text += "<br/>";
      }
    }
  }

  UnstackStyle();
  UnstackStyle();

  if (hasTiming)
    StackSubtitle("child_span", beginTime, endTime, text);
  else
    subText += text;
}

void TTML2SRT::AppendStyledText(std::string_view textPart, std::string& subText)
{
  if (!textPart.empty())
  {
    std::string strFmt;
    std::string strFmtEnd;
    Style& curStyle = m_styleStack.back();

    if (!curStyle.color.empty())
    {
      strFmt = "<font color=\"" + curStyle.color + "\">";
      strFmtEnd = "</font>";
    }
    if (curStyle.isFontBold.has_value() && *curStyle.isFontBold)
    {
      strFmt += "<b>";
      strFmtEnd = "</b>" + strFmtEnd;
    }
    if (curStyle.isFontItalic.has_value() && *curStyle.isFontItalic)
    {
      strFmt += "<i>";
      strFmtEnd = "</i>" + strFmtEnd;
    }
    if (curStyle.isFontUnderline.has_value() && *curStyle.isFontUnderline)
    {
      strFmt += "<u>";
      strFmtEnd = "</u>" + strFmtEnd;
    }

    subText += strFmt;
    subText += textPart;
    subText += strFmtEnd;
  }
}

TTML2SRT::Style TTML2SRT::ParseStyle(pugi::xml_node node)
{
  Style style;

  style.id = XML::GetAttrib(node, "xml:id");
  style.color = XML::GetAttrib(node, "tts:color");

  // Subtitles that make use of images to show text are not supported
  if (node.attribute("tts:backgroundImage"))
  {
    LOG::LogF(LOGWARNING,
              "The \"backgroundImage\" attribute to show subtitles images is not supported.");
  }

  std::string styleVal;
  if (XML::QueryAttrib(node, "tts:textDecoration", styleVal))
  {
    if (styleVal == "underline")
      style.isFontUnderline = true;
    else if (styleVal == "noUnderline")
      style.isFontUnderline = false;
  }

  if (XML::QueryAttrib(node, "tts:fontStyle", styleVal))
  {
    if (styleVal == "italic")
      style.isFontItalic = true;
    else if (styleVal == "normal")
      style.isFontItalic = false;
  }

  if (XML::QueryAttrib(node, "tts:fontWeight", styleVal))
  {
    if (styleVal == "bold")
      style.isFontBold = true;
    else if (styleVal == "normal")
      style.isFontBold = false;
  }
  return style;
}

void TTML2SRT::StackStyle(const Style& style)
{
  // Get last style add and merge with the style found
  Style newStyle = m_styleStack.back();

  if (!style.id.empty())
  {
    if (style.id.empty())
      newStyle.id += "_nested";
    else
      newStyle.id = style.id;
  }

  if (!style.color.empty())
    newStyle.color = style.color;

  if (style.isFontBold.has_value())
    newStyle.isFontBold = style.isFontBold;

  if (style.isFontItalic.has_value())
    newStyle.isFontItalic = style.isFontItalic;

  if (style.isFontUnderline.has_value())
    newStyle.isFontUnderline = style.isFontUnderline;

  m_styleStack.emplace_back(newStyle);
}

void TTML2SRT::StackStyle(std::string_view styleId)
{
  if (!styleId.empty())
  {
    auto itStyle = std::find_if(m_styles.begin(), m_styles.end(),
                                [&styleId](const Style& item) { return item.id == styleId; });

    if (itStyle != m_styles.end())
    {
      // Get last style add and merge with the style found
      Style newStyle = m_styleStack.back();

      if (!itStyle->id.empty())
        newStyle.id = itStyle->id;

      if (!itStyle->color.empty())
        newStyle.color = itStyle->color;

      if (itStyle->isFontBold.has_value())
        newStyle.isFontBold = itStyle->isFontBold;

      if (itStyle->isFontItalic.has_value())
        newStyle.isFontItalic = itStyle->isFontItalic;

      if (itStyle->isFontUnderline.has_value())
        newStyle.isFontUnderline = itStyle->isFontUnderline;

      m_styleStack.emplace_back(newStyle);
      return;
    }
  }
  m_styleStack.emplace_back(m_styleStack.back());
}

void TTML2SRT::UnstackStyle()
{
  m_styleStack.pop_back();
}

void TTML2SRT::StackSubtitle(std::string_view id,
                             std::string_view beginTime,
                             std::string_view endTime,
                             std::string_view text)
{
  if (beginTime.empty() || endTime.empty())
    return;

  // Don't stack subtitle if begin and end are equal
  if (beginTime == endTime)
    return;

  SubtitleData newSub;
  newSub.start = GetTime(std::string(beginTime));
  newSub.end = GetTime(std::string(endTime));
  newSub.text = text;

  if (!m_subtitlesList.empty() && !newSub.text.empty())
  {
    // This is a workaround for Kodi overlapped subtitles rendering,
    // when there are multiple lines of text provided by multiple "p" elements
    // usually with same begin/end timings (overlapping)
    // the subtitle renderer show on screen these lines of text in "reversed order"
    // (last added on top, the first on bottom) that is the SRT behaviour,
    // and causes the display of inverted sentences with TTML.
    // So TTML multilines should be shown "as is" as it appears in the xml file.
    // The workaround consists in to merge these lines with same begin/end timing,
    // but can fail when the end time is different or if "p" elements come from different media segments.

    //! @todo: a better solution should come from the libass library, but it is also possible that converting
    //! TTML directly to ASS format (and use CDVDOverlayCodecSSA decoder) may solve the problem, need a test.
    SubtitleData& lastSub = m_subtitlesList.back();
    if (lastSub.start == newSub.start && lastSub.end == newSub.end)
    {
      lastSub.text += "<br/>" + newSub.text;
      return;
    }
  }

  m_subtitlesList.emplace_back(newSub);
}

uint64_t TTML2SRT::GetTime(std::string timeExpr)
{
  uint64_t ts{0};
  unsigned long long h{0};
  unsigned long long m{0};
  unsigned long long s{0};
  unsigned long long ms{0};
  unsigned long long f{0};
  unsigned long long sf{0};

  // Tick metric, cannot be fractional
  if (timeExpr.back() == 't')
  {
    timeExpr.pop_back();
    ts = STRING::ToUint64(timeExpr) * m_timescale;
    if (m_tickRate > 0)
      ts /= m_tickRate;
  }
  // Hours metric, can be fractional
  else if (timeExpr.back() == 'h')
  {
    timeExpr.pop_back();
    ts = static_cast<uint64_t>(STRING::ToDouble(timeExpr) * m_timescale * 3600);
  }
  // Minutes metric, can be fractional
  else if (timeExpr.back() == 'm')
  {
    timeExpr.pop_back();
    ts = static_cast<uint64_t>(STRING::ToDouble(timeExpr) * m_timescale * 60);
  }
  // Milliseconds or secods metric
  else if (timeExpr.back() == 's')
  {
    timeExpr.pop_back();
    // Milliseconds metric, can be fractional but we work at 1ms
    if (timeExpr.back() == 'm')
    {
      timeExpr.pop_back();
      ts = STRING::ToUint64(timeExpr);
    }
    else // Seconds metric, can be fractional
    {
      ts = static_cast<uint64_t>(STRING::ToDouble(timeExpr) * m_timescale);
    }
  }
  // Frames metric, can be fractional
  else if (timeExpr.back() == 'f')
  {
    timeExpr.pop_back();

    if (sscanf(timeExpr.c_str(), "%llu.%llu", &f, &sf) != 2)
    {
      f = STRING::ToUint64(timeExpr);
    }

    if (m_frameRateNum == NO_VALUE)
    {
      LOG::LogF(LOGDEBUG, "Cue time indicates frames but no frame rate set, assuming 25 FPS");
      m_frameRateNum = 25;
      m_frameRateDen = 1;
    }

    ts = (m_timescale * f * m_frameRateDen) / m_frameRateNum;

    if (sf > 0)
    {
      if (m_subFrameRate == NO_VALUE || m_subFrameRate == 0)
      {
        LOG::LogF(LOGDEBUG, "Cue time indicates sub-frames but no subFrameRate set, assuming 1");
        m_subFrameRate = 1;
      }
      ts += (m_timescale * sf * m_frameRateDen / m_subFrameRate) / m_frameRateNum;
    }
  }
  else if (sscanf(timeExpr.c_str(), "%llu:%llu:%llu.%llu", &h, &m, &s, &ms) == 4)
  {
    ts = (h * 3600 + m * 60 + s) * m_timescale + ms;
  }
  else if (sscanf(timeExpr.c_str(), "%llu:%llu:%llu:%llu.%llu", &h, &m, &s, &f, &sf) == 5)
  {
    ts = (h * 3600 + m * 60 + s) * m_timescale;

    if (m_frameRateNum == NO_VALUE)
    {
      LOG::LogF(LOGDEBUG, "Cue time indicates frames but no frame rate set, assuming 25 FPS");
      m_frameRateNum = 25;
      m_frameRateDen = 1;
    }
    if (m_subFrameRate == NO_VALUE || m_subFrameRate == 0)
    {
      LOG::LogF(LOGDEBUG, "Cue time indicates sub-frames but no subFrameRate set, assuming 1");
      m_subFrameRate = 1;
    }

    ts += (m_timescale * f * m_frameRateDen) / m_frameRateNum;
    ts += (m_timescale * sf * m_frameRateDen / m_subFrameRate) / m_frameRateNum;
  }
  else if (sscanf(timeExpr.c_str(), "%llu:%llu:%llu:%llu", &h, &m, &s, &f) == 4)
  {
    ts = (h * 3600 + m * 60 + s) * m_timescale;

    if (m_frameRateNum == NO_VALUE)
    {
      LOG::LogF(LOGDEBUG, "Cue time indicates frames but no frame rate set, assuming 25 FPS");
      m_frameRateNum = 25;
      m_frameRateDen = 1;
    }

    ts += (m_timescale * f * m_frameRateDen) / m_frameRateNum;
  }
  else if (sscanf(timeExpr.c_str(), "%llu:%llu:%llu", &h, &m, &s) == 3)
  {
    ts = (h * 3600 + m * 60 + s) * m_timescale;
  }
  return ts;
}
