/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "ReprSelector.h"

#include "AdaptationSet.h"
#include "Representation.h"

#include <algorithm>
#include <vector>

using namespace CHOOSER;
using namespace PLAYLIST;

CRepresentationSelector::CRepresentationSelector(const int& resWidth, const int& resHeight)
{
  m_screenWidth = resWidth;
  m_screenHeight = resHeight;
}

PLAYLIST::CRepresentation* CRepresentationSelector::Lowest(PLAYLIST::CAdaptationSet* adaptSet) const
{
  auto& reps = adaptSet->GetRepresentations();
  return reps.empty() ? nullptr : reps[0].get();
}

PLAYLIST::CRepresentation* CRepresentationSelector::Highest(
    PLAYLIST::CAdaptationSet* adaptSet) const
{
  CRepresentation* highestRep{nullptr};

  for (auto& rep : adaptSet->GetRepresentations())
  {
    if (!rep->isPlayable)
      continue;

    if (rep->GetWidth() <= m_screenWidth && rep->GetHeight() <= m_screenHeight)
    {
      if (!highestRep || (highestRep->GetWidth() <= rep->GetWidth() &&
                          highestRep->GetHeight() <= rep->GetHeight() &&
                          highestRep->GetBandwidth() < rep->GetBandwidth()))
      {
        highestRep = rep.get();
      }
    }
  }

  if (!highestRep)
    return Lowest(adaptSet);

  return highestRep;
}

PLAYLIST::CRepresentation* CRepresentationSelector::HighestBw(
    PLAYLIST::CAdaptationSet* adaptSet) const
{
  CRepresentation* repHigherBw{nullptr};

  for (auto& rep : adaptSet->GetRepresentations())
  {
    if (!rep->isPlayable)
      continue;

    if (!repHigherBw || rep->GetBandwidth() > repHigherBw->GetBandwidth())
    {
      repHigherBw = rep.get();
    }
  }

  return repHigherBw;
}

PLAYLIST::CRepresentation* CRepresentationSelector::Higher(PLAYLIST::CAdaptationSet* adaptSet,
                                                           PLAYLIST::CRepresentation* currRep) const
{
  auto reps = adaptSet->GetRepresentationsPtr();
  auto repIt = std::find_if(
      reps.begin(), reps.end(), [currRep](const auto& rep)
      { return rep->isPlayable && CRepresentation::CompareBandwidthPtr(currRep, rep); });

  if (repIt == reps.end())
    return currRep;

  return *repIt;
}

PLAYLIST::CRepresentation* CHOOSER::CRepresentationSelector::Nearest(
    PLAYLIST::CAdaptationSet* adaptSet) const
{
  PLAYLIST::CRepresentation* nearestRep{nullptr};
  uint32_t smallestDiff = std::numeric_limits<uint32_t>::max();

  for (auto& rep : adaptSet->GetRepresentations())
  {
    if (!rep->isPlayable)
      continue;

    const uint32_t resolutionDiff =
        (rep->GetWidth() > m_screenWidth ? rep->GetWidth() - m_screenWidth
                                         : m_screenWidth - rep->GetWidth()) +
        (rep->GetHeight() > m_screenHeight ? rep->GetHeight() - m_screenHeight
                                           : m_screenHeight - rep->GetHeight());

    if (resolutionDiff < smallestDiff ||
        (resolutionDiff == smallestDiff &&
         (!nearestRep || rep->GetBandwidth() > nearestRep->GetBandwidth())))
    {
      smallestDiff = resolutionDiff;
      nearestRep = rep.get();
    }
  }

  return nearestRep;
}

PLAYLIST::CRepresentation* CHOOSER::CRepresentationSelector::NearestBw(
    PLAYLIST::CAdaptationSet* adaptSet, const PLAYLIST::CRepresentation* currRep) const
{
  return NearestBw(adaptSet, currRep->GetBandwidth());
}

PLAYLIST::CRepresentation* CHOOSER::CRepresentationSelector::NearestBw(
    PLAYLIST::CAdaptationSet* adaptSet, const uint32_t bandwidth) const
{
  PLAYLIST::CRepresentation* nearestRep{nullptr};
  uint32_t smallestDiff = std::numeric_limits<uint32_t>::max();

  for (auto& rep : adaptSet->GetRepresentations())
  {
    if (!rep->isPlayable)
      continue;

    const uint32_t bandwidthDiff = (rep->GetBandwidth() > bandwidth)
                                       ? (rep->GetBandwidth() - bandwidth)
                                       : (bandwidth - rep->GetBandwidth());

    const uint32_t resolutionDiff =
        (rep->GetWidth() > m_screenWidth ? rep->GetWidth() - m_screenWidth
                                         : m_screenWidth - rep->GetWidth()) +
        (rep->GetHeight() > m_screenHeight ? rep->GetHeight() - m_screenHeight
                                           : m_screenHeight - rep->GetHeight());

    const uint32_t combinedDiff = bandwidthDiff + resolutionDiff;

    if (combinedDiff < smallestDiff)
    {
      smallestDiff = combinedDiff;
      nearestRep = rep.get();
    }
  }

  return nearestRep;
}
