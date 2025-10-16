/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "CommonSegAttribs.h"
#include "SegTemplate.h"

#ifdef INPUTSTREAM_TEST_BUILD
#include "test/KodiStubs.h"
#else
#include <kodi/AddonBase.h>
#endif

#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace PLAYLIST
{
// Forward
class CAdaptationSet;

class ATTR_DLL_LOCAL CPeriod : public CCommonSegAttribs
{
public:
  CPeriod();
  ~CPeriod();

  static std::unique_ptr<CPeriod> MakeUniquePtr() { return std::make_unique<CPeriod>(); }

  const std::string& GetId() const { return m_id; }
  void SetId(std::string_view id) { m_id = id; }

  std::string GetBaseUrl() const { return m_baseUrl; }
  void SetBaseUrl(std::string_view baseUrl) { m_baseUrl = baseUrl; }

  /*!
   * \brief Get the period index, a sequential number used to distinguish periods.
   * \return The period index.
   */
  uint32_t GetIndex() const { return m_index; }

  /*!
   * \brief Set the period index.
   */
  void SetIndex(uint32_t index) { m_index = index; }

  /*!
   * \brief Get the sequence number (e.g. discontinuity sequence number on HLS).
   * \return The sequence number.
   */
  uint32_t GetSequence() const { return m_sequence; }

  /*!
   * \brief Set the sequence number (e.g. discontinuity sequence number on HLS).
   */
  void SetSequence(uint32_t sequence) { m_sequence = sequence; }

  /*!
   * \brief Get the start time, in ms.
   * \return The start time value, otherwise NO_VALUE if not set.
   */
  uint64_t GetStart() const { return m_start; }

  /*!
   * \brief Set the start time in ms, or NO_VALUE for not set.
   */
  void SetStart(uint64_t start) { m_start = start; }

  /*!
   * \brief Get the duration, in timescale units.
   * \return The duration value.
   */
  uint64_t GetDuration() const { return m_duration; }

  /*!
   * \brief Set the duration, in timescale units.
   */
  void SetDuration(uint64_t duration) { m_duration = duration; }

  /*!
   * \brief Get the timeline duration (constantly updated for live stream), in timescale units.
   * \return The duration value.
   */
  uint64_t GetTlDuration() const { return m_tlDuration; }

  /*!
   * \brief Set the timeline duration, in timescale units.
   */
  void SetTlDuration(uint64_t duration) { m_tlDuration = duration; }

  /*!
   * \brief Get the timescale unit.
   * \return The timescale unit, if not set default value is 1000.
   */
  uint32_t GetTimescale() const { return m_timescale; }

  /*!
   * \brief Set the timescale unit.
   */
  void SetTimescale(uint32_t timescale) { m_timescale = timescale; }

  // Force the use of secure decoder only when parsed manifest specify it
  std::optional<bool> IsSecureDecodeNeeded() const { return m_isSecureDecoderNeeded; }
  void SetSecureDecodeNeeded(std::optional<bool> isSecureDecoderNeeded)
  {
    m_isSecureDecoderNeeded = isSecureDecoderNeeded;
  };

  std::vector<uint32_t>& SegmentTimelineDuration() { return m_segmentTimelineDuration; }
  bool HasSegmentTimelineDuration() { return !m_segmentTimelineDuration.empty(); }

  void CopyHLSData(const CPeriod* other);

  void AddAdaptationSet(std::unique_ptr<CAdaptationSet>& adaptationSet);
  std::vector<std::unique_ptr<CAdaptationSet>>& GetAdaptationSets() { return m_adaptationSets; }

  /*!
   * \brief Determines whether the period is within the specified PTS range.
   * \param ptsMs The PTS in ms
   * \return True when within the specified PTS or true when the
   *         period duration in unknown, otherwise false.
   */
  bool IsInRange(uint64_t ptsMs) const;

  // Make use of PLAYLIST::StreamType flags
  uint32_t m_includedStreamType{0}; //! @todo: part of this need a rework

protected:
  std::vector<std::unique_ptr<CAdaptationSet>> m_adaptationSets;

  std::string m_id;
  std::string m_baseUrl;
  uint32_t m_timescale{1000};
  uint32_t m_sequence{0};
  uint32_t m_index{0};
  uint64_t m_start{NO_VALUE};
  uint64_t m_duration{0};
  uint64_t m_tlDuration{0};

  std::optional<bool> m_isSecureDecoderNeeded;
  std::vector<uint32_t> m_segmentTimelineDuration;
};

} // namespace adaptive
