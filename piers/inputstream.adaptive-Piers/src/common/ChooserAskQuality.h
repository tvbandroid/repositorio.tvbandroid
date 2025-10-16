/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "Chooser.h"

namespace CHOOSER
{
/*!
 * \brief The quality of the stream is asked to the user by a dialog window
 */
class ATTR_DLL_LOCAL CRepresentationChooserAskQuality : public IRepresentationChooser
{
public:
  CRepresentationChooserAskQuality();
  ~CRepresentationChooserAskQuality() override {}

  void Initialize(const ADP::KODI_PROPS::ChooserProps& props) override;

  void PostInit() override;

  PLAYLIST::CAdaptationSet* GetPreferredVideoAdpSet(
      PLAYLIST::CPeriod* period, PLAYLIST::CAdaptationSet* adpSetPreferred) override;

  PLAYLIST::CRepresentation* GetNextRepresentation(PLAYLIST::CAdaptationSet* adp,
                                                   PLAYLIST::CRepresentation* currentRep) override;

private:
  bool m_isDialogShown{false};
  std::pair<int, int> m_resRangeLimit;
  int m_selectedResWidth{0};
  int m_selectedResHeight{0};
  uint32_t m_selectedBandwidth{0};
  std::string m_selectedVideoCodecDesc;
};

} // namespace CHOOSER
