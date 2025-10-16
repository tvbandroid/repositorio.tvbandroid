/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "CodecHandler.h"

class ATTR_DLL_LOCAL HEVCCodecHandler : public CodecHandler
{
public:
  HEVCCodecHandler(AP4_SampleDescription* sd, AP4_Track* track = nullptr);

  bool CheckExtraData(std::vector<uint8_t>& extraData, bool isRequiredAnnexB) override;
  bool GetInformation(kodi::addon::InputstreamInfo& info) override;
};
