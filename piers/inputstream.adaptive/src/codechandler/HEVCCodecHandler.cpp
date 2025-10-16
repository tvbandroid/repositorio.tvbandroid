/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "HEVCCodecHandler.h"

#include "utils/log.h"
#include "utils/Utils.h"

using namespace UTILS;

HEVCCodecHandler::HEVCCodecHandler(AP4_SampleDescription* sd, AP4_Track* track)
  : CodecHandler(sd, track)
{
  if (AP4_HevcSampleDescription* hevcSampleDescription =
          AP4_DYNAMIC_CAST(AP4_HevcSampleDescription, m_sampleDescription))
  {
    const AP4_DataBuffer& rawBytes = hevcSampleDescription->GetRawBytes();
    m_extraData.assign(rawBytes.GetData(), rawBytes.GetData() + rawBytes.GetDataSize());

    m_naluLengthSize = hevcSampleDescription->GetNaluLengthSize();
  }
}

bool HEVCCodecHandler::CheckExtraData(std::vector<uint8_t>& extraData, bool isRequiredAnnexB)
{
  if (extraData.empty())
    return false;

  // Make sure that extradata is in the required format
  if (isRequiredAnnexB && !UTILS::IsAnnexB(extraData))
  {
    extraData = UTILS::HvccToAnnexb(extraData);
    return true;
  }
  if (!isRequiredAnnexB && UTILS::IsAnnexB(extraData))
  {
    extraData = UTILS::AnnexbToHvcc(extraData);
    return true;
  }

  return false;
}

bool HEVCCodecHandler::GetInformation(kodi::addon::InputstreamInfo& info)
{
  bool isChanged = UpdateInfoCodecName(info, CODEC::FOURCC_HEVC);

  uint32_t fourcc{0};
  switch (m_sampleDescription->GetFormat())
  {
    case AP4_SAMPLE_FORMAT_HEV1:
      fourcc = CODEC::MakeFourCC(CODEC::FOURCC_HEV1);
      break;
    case AP4_SAMPLE_FORMAT_HVC1:
      fourcc = CODEC::MakeFourCC(CODEC::FOURCC_HVC1);
      break;
    case AP4_SAMPLE_FORMAT_DVHE:
      fourcc = CODEC::MakeFourCC(CODEC::FOURCC_DVHE);
      break;
    case AP4_SAMPLE_FORMAT_DVH1:
      fourcc = CODEC::MakeFourCC(CODEC::FOURCC_DVH1);
      break;
    default:
      break;
  }
  if (fourcc > 0 && info.GetCodecFourCC() != fourcc)
  {
    info.SetCodecFourCC(fourcc);
    isChanged = true;
  }

  if (info.GetFpsRate() == 0)
  {
    if (AP4_HevcSampleDescription* hevcSampleDescription =
            AP4_DYNAMIC_CAST(AP4_HevcSampleDescription, m_sampleDescription))
    {
      if (hevcSampleDescription->GetAverageFrameRate() > 0)
      {
        info.SetFpsRate(hevcSampleDescription->GetAverageFrameRate());
        info.SetFpsScale(256);
        isChanged = true;
      }
      else if (hevcSampleDescription->GetConstantFrameRate() > 0)
      {
        info.SetFpsRate(hevcSampleDescription->GetConstantFrameRate());
        info.SetFpsScale(256);
        isChanged = true;
      }
    }
  }

  // store dvcc metadata
  if (auto dvcc = ParseDvcc())
  {
    PopulateDvccMetadata(info, dvcc, isChanged);
  }

  return isChanged;
}
