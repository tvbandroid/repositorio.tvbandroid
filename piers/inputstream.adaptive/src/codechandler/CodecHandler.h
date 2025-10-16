/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include <bento4/Ap4.h>

#ifdef INPUTSTREAM_TEST_BUILD
#include "test/KodiStubs.h"
#else
#include <kodi/AddonBase.h>
#include <kodi/addon-instance/Inputstream.h>
#endif

#include <cstdint>
#include <vector>

class ATTR_DLL_LOCAL CodecHandler
{
public:
  CodecHandler(AP4_SampleDescription* sd, AP4_Track* track = nullptr)
    : m_sampleDescription(sd), m_naluLengthSize(0), m_pictureId(0), m_pictureIdPrev(0xFF),
      m_track(track){};
  virtual ~CodecHandler(){};

  virtual void UpdatePPSId(const AP4_DataBuffer& buffer) {}

  /*!
   * \brief Query the codec handler to get stream info. It can provide info that are missing
   *        from the manifest metadata and/or correct wrong info provided by malformed manifests.
   * \param info The object where set the info
   * \return True if some info is changed, otherwise false
   */
  virtual bool GetInformation(kodi::addon::InputstreamInfo& info);

  /*!
   * \brief Check for extradata data format, if needed it will be converted
   * \param extraData The data
   * \param isRequiredAnnexB If the extradata must be in annex b format
   * \return True if data is changed, otherwise false
   */
  virtual bool CheckExtraData(std::vector<uint8_t>& extraData, bool isRequiredAnnexB)
  {
    return false;
  }
  virtual STREAMCODEC_PROFILE GetProfile() { return STREAMCODEC_PROFILE::CodecProfileNotNeeded; };
  virtual bool Transform(AP4_UI64 pts, AP4_UI32 duration, AP4_DataBuffer& buf, AP4_UI64 timescale)
  {
    return false;
  };
  virtual bool ReadNextSample(AP4_Sample& sample, AP4_DataBuffer& buf) { return false; };
  virtual void SetPTSOffset(AP4_UI64 offset){};
  virtual bool TimeSeek(AP4_UI64 seekPos) { return true; };
  virtual void Reset(){};

  AP4_DvccAtom* ParseDvcc();
  void PopulateDvccMetadata(kodi::addon::InputstreamInfo& info,
                            AP4_DvccAtom* dvcc,
                            bool& isChanged);

  AP4_SampleDescription* m_sampleDescription;
  std::vector<uint8_t> m_extraData;
  AP4_UI08 m_naluLengthSize;
  AP4_UI08 m_pictureId;
  AP4_UI08 m_pictureIdPrev;
  AP4_Track* m_track;

  protected:
  bool UpdateInfoCodecName(kodi::addon::InputstreamInfo& info, const char* codecName);
};
