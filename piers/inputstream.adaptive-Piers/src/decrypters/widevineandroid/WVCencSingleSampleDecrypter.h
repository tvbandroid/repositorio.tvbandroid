/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "common/AdaptiveCencSampleDecrypter.h"
#include "decrypters/HelperWv.h"
#include "decrypters/IDecrypter.h"

#include <map>
#include <string_view>

namespace jni
{
class CJNIMediaDrm;
}

class ATTR_DLL_LOCAL CWVCencSingleSampleDecrypterA : public Adaptive_CencSingleSampleDecrypter,
                                                     public IWVObserver
{
public:
  CWVCencSingleSampleDecrypterA(IWVCdmAdapter<jni::CJNIMediaDrm>* cdmAdapter,
                                const std::vector<uint8_t>& pssh,
                                const std::vector<uint8_t>& defaultKeyId);
  virtual ~CWVCencSingleSampleDecrypterA();

  bool StartSession(bool skipSessionMessage) { return KeyUpdateRequest(true, skipSessionMessage); };

  virtual std::string GetSessionId() override;
  std::vector<uint8_t> GetChallengeData();

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

  void GetCapabilities(const std::vector<uint8_t>& keyId, DRM::DecrypterCapabilites& caps);

  void RequestNewKeys() { m_isKeyUpdateRequested = true; };

  // IWVObserver interface
  void OnNotify(const CdmMessage& message) override;

private:
  bool ProvisionRequest();
  bool GetKeyRequest(std::vector<uint8_t>& keyRequestData);
  bool KeyUpdateRequest(bool waitForKeys, bool skipSessionMessage);
  bool SendSessionMessage(const std::vector<uint8_t>& challenge);

  IWVCdmAdapter<jni::CJNIMediaDrm>* m_cdmAdapter;

  std::vector<uint8_t> m_pssh;
  std::vector<uint8_t> m_initialPssh;
  std::map<std::string, std::string> m_optParams;

  std::string m_sessionId;
  std::vector<char> m_sessionIdVec;
  std::vector<char> m_keySetId;
  std::vector<uint8_t> m_keyRequestData;

  bool m_isProvisioningRequested;
  bool m_isKeyUpdateRequested;

  std::vector<uint8_t> m_defaultKeyId;

  struct FINFO
  {
    std::vector<uint8_t> m_key;
    AP4_UI08 m_nalLengthSize;
    AP4_UI16 m_decrypterFlags;
    std::vector<uint8_t> m_annexbSpsPps;
  };
  std::vector<FINFO> m_fragmentPool;

  uint16_t m_hdcpVersion{DRM::HDCP_V_MAX};
  int m_hdcpLimit{0};
  int m_resolutionLimit{0};
};
