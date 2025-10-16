/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "cdm/media/cdm/api/content_decryption_module.h"
#include "common/AdaptiveCencSampleDecrypter.h"
#include "decrypters/HelperWv.h"
#include "decrypters/IDecrypter.h"

#include <list>
#include <mutex>
#include <optional>

namespace media
{
class CdmAdapter;
class CdmVideoFrame;
}

using namespace DRM;

class ATTR_DLL_LOCAL CWVCencSingleSampleDecrypter : public Adaptive_CencSingleSampleDecrypter,
                                                    public IWVObserver
{
public:
  CWVCencSingleSampleDecrypter(IWVCdmAdapter<media::CdmAdapter>* cdmAdapter,
                               const std::vector<uint8_t>& pssh,
                               const std::vector<uint8_t>& defaultKeyId,
                               bool skipSessionMessage,
                               CryptoMode cryptoMode);
  virtual ~CWVCencSingleSampleDecrypter();

  void GetCapabilities(const std::vector<uint8_t>& keyId,
                       DecrypterCapabilites& caps,
                       DRMMediaType mediaType);
  virtual std::string GetSessionId() override;
  void CloseSessionId();
  AP4_DataBuffer GetChallengeData();

  void SetSession(const std::string sessionId, const uint8_t* data, const size_t dataSize);

  void AddSessionKey(const uint8_t* data, size_t dataSize, uint32_t status);
  bool HasKeyId(const std::vector<uint8_t>& keyid);

  virtual AP4_Result SetFragmentInfo(AP4_UI32 poolId,
                                     const std::vector<uint8_t>& keyId,
                                     const AP4_UI08 nalLengthSize,
                                     const std::vector<uint8_t>& annexbSpsPps,
                                     AP4_UI32 flags,
                                     CryptoInfo cryptoInfo) override;
  virtual AP4_UI32 AddPool() override;
  virtual void RemovePool(AP4_UI32 poolId) override;

  virtual AP4_Result DecryptSampleData(
      AP4_UI32 poolId,
      AP4_DataBuffer& dataIn,
      AP4_DataBuffer& dataOut,

      // always 16 bytes
      const AP4_UI08* iv,

      // pass 0 for full decryption
      unsigned int subsampleCount,

      // array of <subsample_count> integers. NULL if subsample_count is 0
      const AP4_UI16* bytesOfCleartextData,

      // array of <subsample_count> integers. NULL if subsample_count is 0
      const AP4_UI32* bytesOfEncryptedData,

      DRM::DRMMediaType streamType) override;

  bool OpenVideoDecoder(const VIDEOCODEC_INITDATA* initData);
  VIDEOCODEC_RETVAL DecryptAndDecodeVideo(kodi::addon::CInstanceVideoCodec* codecInstance,
                                          const DEMUX_PACKET* sample);
  VIDEOCODEC_RETVAL VideoFrameDataToPicture(kodi::addon::CInstanceVideoCodec* codecInstance,
                                            VIDEOCODEC_PICTURE* picture);
  void ResetVideo();
  void SetDefaultKeyId(const std::vector<uint8_t>& keyId) override;
  void AddKeyId(const std::vector<uint8_t>& keyId) override;

  // IWVObserver interface
  void OnNotify(const CdmMessage& message) override;

private:
  void CheckLicenseRenewal();
  bool SendSessionMessage();

  IWVCdmAdapter<media::CdmAdapter>* m_cdmAdapter;
  std::string m_strSession;
  std::vector<uint8_t> m_pssh;
  AP4_DataBuffer m_challenge;
  std::vector<uint8_t> m_defaultKeyId;
  struct WVSKEY
  {
    bool operator==(WVSKEY const& other) const { return m_keyId == other.m_keyId; };
    std::vector<uint8_t> m_keyId;
    cdm::KeyStatus status;
  };
  std::vector<WVSKEY> m_keys;

  uint16_t m_hdcpVersion{DRM::HDCP_V_MAX};
  int m_hdcpLimit{0};
  int m_resolutionLimit{0};

  AP4_DataBuffer m_decryptIn;
  AP4_DataBuffer m_decryptOut;

  struct FINFO
  {
    std::vector<uint8_t> m_key;
    AP4_UI08 m_nalLengthSize;
    AP4_UI16 m_decrypterFlags;
    std::vector<uint8_t> m_annexbSpsPps;
    CryptoInfo m_cryptoInfo;
  };
  std::vector<FINFO> m_fragmentPool;
  void LogDecryptError(const cdm::Status status, const std::vector<uint8_t>& keyId);
  void SetCdmSubsamples(std::vector<cdm::SubsampleEntry>& subsamples, bool isCbc);
  void RepackSubsampleData(AP4_DataBuffer& dataIn,
                           AP4_DataBuffer& dataOut,
                           size_t& startPos,
                           size_t& cipherPos,
                           const size_t subsamplePos,
                           const AP4_UI16* bytesOfCleartextData,
                           const AP4_UI32* bytesOfEncryptedData);
  void UnpackSubsampleData(AP4_DataBuffer& dataIn,
                           size_t& startPos,
                           const size_t subsamplePos,
                           const AP4_UI16* bytesOfCleartextData,
                           const AP4_UI32* bytesOfEncryptedData);
  void SetInput(cdm::InputBuffer_2& cdmInputBuffer,
                const AP4_DataBuffer& inputData,
                const unsigned int subsampleCount,
                const uint8_t* iv,
                const FINFO& fragInfo,
                const std::vector<cdm::SubsampleEntry>& subsamples);
  AP4_Result ConvertToAnnexBandInject(AP4_DataBuffer& dataIn,
                                      AP4_DataBuffer& dataOut,
                                      unsigned int subsampleCount,
                                      FINFO& fragInfo,
                                      const AP4_UI08* iv,
                                      const AP4_UI16* bytesOfCleartextData,
                                      const AP4_UI32* bytesOfEncryptedData,
                                      bool convertAnnexB,
                                      std::vector<cdm::SubsampleEntry>& rebuiltSubs);

  uint32_t m_promiseId;
  bool m_isDrained;

  std::list<media::CdmVideoFrame> m_videoFrames;
  std::mutex m_renewalLock;
  CryptoMode m_EncryptionMode;

  std::optional<cdm::VideoDecoderConfig_3> m_currentVideoDecConfig;
};
