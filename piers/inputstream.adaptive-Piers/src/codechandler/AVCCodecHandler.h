/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "CodecHandler.h"

class ATTR_DLL_LOCAL AVCCodecHandler : public CodecHandler
{
public:
  AVCCodecHandler(AP4_SampleDescription* sd);

  bool CheckExtraData(std::vector<uint8_t>& extraData, bool isRequiredAnnexB) override;
  void UpdatePPSId(const AP4_DataBuffer& buffer) override;
  bool GetInformation(kodi::addon::InputstreamInfo& info) override;
  STREAMCODEC_PROFILE GetProfile() override { return m_codecProfile; };

private:
  unsigned int m_countPictureSetIds;
  bool m_needSliceInfo;
  STREAMCODEC_PROFILE m_codecProfile;
};
