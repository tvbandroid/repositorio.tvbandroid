/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "CodecHandler.h"

namespace
{
constexpr const char* NETFLIX_FRAMERATE_UUID = "NetflixFrameRate";
}

bool CodecHandler::GetInformation(kodi::addon::InputstreamInfo& info)
{
  if (m_sampleDescription->GetType() != AP4_SampleDescription::Type::TYPE_SUBTITLES &&
      m_sampleDescription->GetType() != AP4_SampleDescription::Type::TYPE_UNKNOWN)
  {
    // Netflix Framerate
    AP4_Atom* atom;
    AP4_UnknownUuidAtom* nxfr;
    atom = m_sampleDescription->GetDetails().GetChild(
        reinterpret_cast<const AP4_UI08*>(NETFLIX_FRAMERATE_UUID));
    if (atom && (nxfr = dynamic_cast<AP4_UnknownUuidAtom*>(atom)) &&
        nxfr->GetData().GetDataSize() == 10)
    {
      unsigned int fpsRate = nxfr->GetData().GetData()[7] | nxfr->GetData().GetData()[6] << 8;
      unsigned int fpsScale = nxfr->GetData().GetData()[9] | nxfr->GetData().GetData()[8] << 8;

      if (info.GetFpsScale() != fpsScale || info.GetFpsRate() != fpsRate)
      {
        info.SetFpsScale(fpsScale);
        info.SetFpsRate(fpsRate);
        return true;
      }
    }
  }
  return false;
}

bool CodecHandler::UpdateInfoCodecName(kodi::addon::InputstreamInfo& info, const char* codecName)
{
  bool isChanged{false};

  if (info.GetCodecName() != codecName)
  {
    info.SetCodecName(codecName);
    isChanged = true;
  }

  AP4_String codecStr;
  m_sampleDescription->GetCodecString(codecStr);
  if (isChanged && codecStr.GetLength() > 0 && info.GetCodecInternalName() != codecStr.GetChars())
  {
    info.SetCodecInternalName(codecStr.GetChars());
    isChanged = true;
  }

  return isChanged;
};

AP4_DvccAtom* CodecHandler::ParseDvcc()
{
  if (!m_track)
    return nullptr;

  if (AP4_TrakAtom* trak = m_track->UseTrakAtom())
  {
    if (auto mdia = AP4_DYNAMIC_CAST(AP4_ContainerAtom, trak->GetChild(AP4_ATOM_TYPE_MDIA, 0)))
    {
      if (auto minf = AP4_DYNAMIC_CAST(AP4_ContainerAtom, mdia->GetChild(AP4_ATOM_TYPE_MINF, 0)))
      {
        if (auto stbl = AP4_DYNAMIC_CAST(AP4_ContainerAtom, minf->GetChild(AP4_ATOM_TYPE_STBL, 0)))
        {
          if (auto stsd =
                  AP4_DYNAMIC_CAST(AP4_ContainerAtom, stbl->GetChild(AP4_ATOM_TYPE_STSD, 0)))
          {
            for (auto* eitem = stsd->GetChildren().FirstItem(); eitem; eitem = eitem->GetNext())
            {
              auto entry_ctn = AP4_DYNAMIC_CAST(AP4_ContainerAtom, eitem->GetData());

              if (!entry_ctn)
                continue;
              AP4_Atom* dv_atom = entry_ctn->GetChild(AP4_ATOM_TYPE_DVCC, 0);
              if (!dv_atom)
                dv_atom = entry_ctn->GetChild(AP4_ATOM_TYPE_DVVC, 0);
              if (!dv_atom)
                continue;

              if (auto dvcc = AP4_DYNAMIC_CAST(AP4_DvccAtom, dv_atom))
              {
                return dvcc;
              }
            }
          }
        }
      }
    }
  }

  return nullptr;
}

void CodecHandler::PopulateDvccMetadata(kodi::addon::InputstreamInfo& info,
                                        AP4_DvccAtom* dvcc,
                                        bool& isChanged)
{
  if (!dvcc)
    return;

  kodi::addon::InputstreamDvccMetadata meta;
  meta.SetDvVersionMajor(dvcc->GetDvVersionMajor());
  meta.SetDvVersionMinor(dvcc->GetDvVersionMinor());
  meta.SetDvProfile(dvcc->GetDvProfile());
  meta.SetDvLevel(dvcc->GetDvLevel());
  meta.SetRpuPresentFlag(dvcc->GetRpuPresentFlag());
  meta.SetElPresentFlag(dvcc->GetElPresentFlag());
  meta.SetBlPresentFlag(dvcc->GetBlPresentFlag());
  meta.SetBlSignalCompatibilityId(dvcc->GetDvBlSignalCompatibilityID());

  if (!(meta == info.GetDvccMetadata()))
  {
    info.SetDvccMetadata(meta);
    isChanged = true;
  }
}
