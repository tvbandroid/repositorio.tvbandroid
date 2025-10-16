/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "AdaptiveDecrypter.h"
#include "decrypters/DrmEngineDefines.h"

#include <memory>

#include <bento4/Ap4.h>

class CAdaptiveCencSampleDecrypter : public AP4_CencSampleDecrypter
{
public:
  CAdaptiveCencSampleDecrypter(std::shared_ptr<Adaptive_CencSingleSampleDecrypter> singleSampleDecrypter,
                               AP4_CencSampleInfoTable* sampleInfoTable);
  ~CAdaptiveCencSampleDecrypter() override {};

  virtual AP4_Result DecryptSampleData(AP4_UI32 poolid,
                                       AP4_DataBuffer& data_in,
                                       AP4_DataBuffer& data_out,
                                       const AP4_UI08* iv,
                                       DRM::DRMMediaType streamType);

protected:
  std::shared_ptr<Adaptive_CencSingleSampleDecrypter> m_decrypter;
};
