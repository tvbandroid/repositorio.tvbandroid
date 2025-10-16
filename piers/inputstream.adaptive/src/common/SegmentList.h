/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "AdaptiveUtils.h"

#ifdef INPUTSTREAM_TEST_BUILD
#include "test/KodiStubs.h"
#else
#include <kodi/AddonBase.h>
#endif

#include <optional>
#include <string>
#include <string_view>

namespace PLAYLIST
{
// Forward
class CSegment;

class ATTR_DLL_LOCAL CSegmentList
{
public:
  CSegmentList() = default;
  ~CSegmentList() = default;

  uint64_t GetStartNumber() const { return m_startNumber; }
  void SetStartNumber(uint64_t startNumber) { m_startNumber = startNumber; }

  uint64_t GetDuration() const { return m_duration; }
  void SetDuration(uint64_t duration) { m_duration = duration; }

  uint32_t GetTimescale() const { return m_timescale; }
  void SetTimescale(uint32_t timescale) { m_timescale = timescale; }

  uint64_t GetPresTimeOffset() const { return m_ptsOffset; }
  void SetPresTimeOffset(uint64_t ptsOffset) { m_ptsOffset = ptsOffset; }

  void SetInitSourceUrl(std::string_view url) { m_initSourceUrl = url; }

  void SetInitRange(const std::string& range);
  bool HasInitialization() { return m_initRangeBegin != NO_VALUE && m_initRangeEnd != NO_VALUE; }
  CSegment MakeInitSegment();

private:
  uint64_t m_startNumber{0};
  uint64_t m_duration{0};
  uint32_t m_timescale{0};
  uint64_t m_ptsOffset{0};
  uint64_t m_initRangeBegin = NO_VALUE;
  uint64_t m_initRangeEnd = NO_VALUE;
  std::string m_initSourceUrl;
};

} // namespace adaptive
