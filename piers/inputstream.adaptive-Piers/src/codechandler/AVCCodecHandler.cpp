/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "AVCCodecHandler.h"

#include "utils/Utils.h"

using namespace UTILS;

AVCCodecHandler::AVCCodecHandler(AP4_SampleDescription* sd)
  : CodecHandler{sd},
    m_countPictureSetIds{0},
    m_needSliceInfo{false},
    m_codecProfile{STREAMCODEC_PROFILE::CodecProfileUnknown}
{
  AP4_UI16 height{0};
  AP4_UI16 width{0};
  if (AP4_VideoSampleDescription* videoSampleDescription =
          AP4_DYNAMIC_CAST(AP4_VideoSampleDescription, m_sampleDescription))
  {
    width = videoSampleDescription->GetWidth();
    height = videoSampleDescription->GetHeight();
  }
  if (AP4_AvcSampleDescription* avcSampleDescription =
          AP4_DYNAMIC_CAST(AP4_AvcSampleDescription, m_sampleDescription))
  {
    const AP4_DataBuffer& rawBytes = avcSampleDescription->GetRawBytes();
    m_extraData.assign(rawBytes.GetData(), rawBytes.GetData() + rawBytes.GetDataSize());

    m_countPictureSetIds = avcSampleDescription->GetPictureParameters().ItemCount();
    m_naluLengthSize = avcSampleDescription->GetNaluLengthSize();
    m_needSliceInfo = (m_countPictureSetIds > 1 || width == 0 || height == 0);
    switch (avcSampleDescription->GetProfile())
    {
      case AP4_AVC_PROFILE_BASELINE:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileBaseline;
        break;
      case AP4_AVC_PROFILE_MAIN:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileMain;
        break;
      case AP4_AVC_PROFILE_EXTENDED:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileExtended;
        break;
      case AP4_AVC_PROFILE_HIGH:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileHigh;
        break;
      case AP4_AVC_PROFILE_HIGH_10:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileHigh10;
        break;
      case AP4_AVC_PROFILE_HIGH_422:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileHigh422;
        break;
      case AP4_AVC_PROFILE_HIGH_444:
        m_codecProfile = STREAMCODEC_PROFILE::H264CodecProfileHigh444Predictive;
        break;
    }
  }
}

bool AVCCodecHandler::CheckExtraData(std::vector<uint8_t>& extraData, bool isRequiredAnnexB)
{
  if (extraData.empty())
    return false;

  // Make sure that extradata is in the required format
  if (isRequiredAnnexB && !UTILS::IsAnnexB(extraData))
  {
    extraData = UTILS::AvcToAnnexb(extraData);
    return true;
  }
  if (!isRequiredAnnexB && UTILS::IsAnnexB(extraData))
  {
    extraData = UTILS::AnnexbToAvc(extraData);
    return true;
  }

  return false;
}

void AVCCodecHandler::UpdatePPSId(const AP4_DataBuffer& buffer)
{
  if (!m_needSliceInfo)
    return;

  //Search the Slice header NALU
  const AP4_Byte* data(buffer.GetData());
  AP4_Size dataSize(buffer.GetDataSize());
  for (; dataSize;)
  {
    // sanity check
    if (dataSize < m_naluLengthSize)
      break;

    // get the next NAL unit
    AP4_UI32 naluSize;
    switch (m_naluLengthSize)
    {
      case 1:
        naluSize = *data++;
        dataSize--;
        break;
      case 2:
        naluSize = AP4_BytesToUInt16BE(data);
        data += 2;
        dataSize -= 2;
        break;
      case 4:
        naluSize = AP4_BytesToUInt32BE(data);
        data += 4;
        dataSize -= 4;
        break;
      default:
        dataSize = 0;
        naluSize = 1;
        break;
    }
    if (naluSize > dataSize)
      break;

    // Stop further NALU processing
    if (m_countPictureSetIds < 2)
      m_needSliceInfo = false;

    unsigned int nal_unit_type = *data & 0x1F;

    if (
        //nal_unit_type == AP4_AVC_NAL_UNIT_TYPE_CODED_SLICE_OF_NON_IDR_PICTURE ||
        nal_unit_type == AP4_AVC_NAL_UNIT_TYPE_CODED_SLICE_OF_IDR_PICTURE //||
        //nal_unit_type == AP4_AVC_NAL_UNIT_TYPE_CODED_SLICE_DATA_PARTITION_A ||
        //nal_unit_type == AP4_AVC_NAL_UNIT_TYPE_CODED_SLICE_DATA_PARTITION_B ||
        //nal_unit_type == AP4_AVC_NAL_UNIT_TYPE_CODED_SLICE_DATA_PARTITION_C
    )
    {
      AP4_DataBuffer unescaped(data, dataSize);
      AP4_NalParser::Unescape(unescaped);
      AP4_BitReader bits(unescaped.GetData(), unescaped.GetDataSize());

      bits.SkipBits(8); // NAL Unit Type

      AP4_AvcFrameParser::ReadGolomb(bits); // first_mb_in_slice
      AP4_AvcFrameParser::ReadGolomb(bits); // slice_type
      m_pictureId = AP4_AvcFrameParser::ReadGolomb(bits); //picture_set_id
    }
    // move to the next NAL unit
    data += naluSize;
    dataSize -= naluSize;
  }
}

bool AVCCodecHandler::GetInformation(kodi::addon::InputstreamInfo& info)
{
  if (m_pictureId == m_pictureIdPrev)
    return false;
  m_pictureIdPrev = m_pictureId;

  bool isChanged = UpdateInfoCodecName(info, CODEC::NAME_H264);

  uint32_t fourcc = 0;
  if (m_sampleDescription->GetFormat() == AP4_SAMPLE_FORMAT_AVC1)
    fourcc = CODEC::MakeFourCC(CODEC::FOURCC_AVC1);
  else if (m_sampleDescription->GetFormat() == AP4_SAMPLE_FORMAT_AVC2)
    fourcc = CODEC::MakeFourCC(CODEC::FOURCC_AVC2);
  else if (m_sampleDescription->GetFormat() == AP4_SAMPLE_FORMAT_AVC3)
    fourcc = CODEC::MakeFourCC(CODEC::FOURCC_AVC3);
  else if (m_sampleDescription->GetFormat() == AP4_SAMPLE_FORMAT_AVC4)
    fourcc = CODEC::MakeFourCC(CODEC::FOURCC_AVC4);

  if (fourcc != 0 && info.GetCodecFourCC() != fourcc)
  {
    info.SetCodecFourCC(fourcc);
    isChanged = true;
  }

  if (AP4_AvcSampleDescription* avcSampleDescription =
          AP4_DYNAMIC_CAST(AP4_AvcSampleDescription, m_sampleDescription))
  {
    AP4_Array<AP4_DataBuffer>& ppsList(avcSampleDescription->GetPictureParameters());
    AP4_AvcPictureParameterSet pps;
    for (unsigned int i(0); i < ppsList.ItemCount(); ++i)
    {
      AP4_AvcFrameParser fp;
      if (AP4_SUCCEEDED(fp.ParsePPS(ppsList[i].GetData(), ppsList[i].GetDataSize(), pps)) &&
          pps.pic_parameter_set_id == m_pictureId)
      {
        AP4_Array<AP4_DataBuffer>& spsList = avcSampleDescription->GetSequenceParameters();
        AP4_AvcSequenceParameterSet sps;
        for (unsigned int i{0}; i < spsList.ItemCount(); ++i)
        {
          if (AP4_SUCCEEDED(fp.ParseSPS(spsList[i].GetData(), spsList[i].GetDataSize(), sps)) &&
              sps.seq_parameter_set_id == pps.seq_parameter_set_id)
          {
            unsigned int width = info.GetWidth();
            unsigned int height = info.GetHeight();
            unsigned int fps_ticks = info.GetFpsRate();
            unsigned int fps_scale = info.GetFpsScale();
            float aspect = info.GetAspect();
            bool haveInfo = sps.GetInfo(width, height);
            haveInfo = sps.GetVUIInfo(fps_ticks, fps_scale, aspect) || haveInfo;
            if (haveInfo)
            {
              info.SetWidth(width);
              info.SetHeight(height);
              info.SetFpsRate(fps_ticks);
              info.SetFpsScale(fps_scale);
              info.SetAspect(aspect);
              isChanged = true;
            }
            break;
          }
        }
        break;
      }
    }
  }
  return isChanged;
};
