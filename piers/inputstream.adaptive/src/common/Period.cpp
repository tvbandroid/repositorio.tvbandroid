/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "Period.h"

#include "AdaptationSet.h"
#include "Representation.h"
#include "utils/log.h"

using namespace PLAYLIST;

PLAYLIST::CPeriod::CPeriod() : CCommonSegAttribs()
{
}

PLAYLIST::CPeriod::~CPeriod()
{
}

void PLAYLIST::CPeriod::CopyHLSData(const CPeriod* other)
{
  m_adaptationSets.reserve(other->m_adaptationSets.size());
  for (const auto& otherAdp : other->m_adaptationSets)
  {
    std::unique_ptr<CAdaptationSet> adp = CAdaptationSet::MakeUniquePtr(this);
    adp->CopyHLSData(otherAdp.get());
    m_adaptationSets.push_back(std::move(adp));
  }

  m_baseUrl = other->m_baseUrl;
  m_id = other->m_id;
  m_timescale = other->m_timescale;
  m_includedStreamType = other->m_includedStreamType;
}

void PLAYLIST::CPeriod::AddAdaptationSet(std::unique_ptr<CAdaptationSet>& adaptationSet)
{
  m_adaptationSets.push_back(std::move(adaptationSet));
}

bool PLAYLIST::CPeriod::IsInRange(uint64_t ptsMs) const
{
  const uint64_t periodDurMs = m_duration * 1000 / m_timescale;

  uint64_t periodEndMs{NO_PTS_VALUE};
  if (periodDurMs != 0)
  {
    const uint64_t start = m_start == NO_VALUE ? 0 : m_start;
    periodEndMs = start + periodDurMs;
  }

  return periodEndMs == NO_PTS_VALUE || periodEndMs > ptsMs;
}
