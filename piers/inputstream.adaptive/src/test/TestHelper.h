/*
 *  Copyright (C) 2021 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "../Iaes_decrypter.h"
#include "../common/AdaptiveStream.h"
#include "../common/Chooser.h"
#include "../common/ChooserDefault.h"
#include "../parser/DASHTree.h"
#include "../parser/HLSTree.h"
#include "../parser/SmoothTree.h"
#include "../utils/log.h"

#include <condition_variable>
#include <mutex>
#include <string_view>

constexpr std::string_view URN_WIDEVINE = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed";

std::string GetEnv(const std::string& var);
void SetFileName(std::string& file, const std::string name);

class testHelper
{
public:
  static bool LoadFile(std::string path, std::string& data);

  static bool DownloadFile(std::string_view url,
                           const std::map<std::string, std::string>& reqHeaders,
                           const std::vector<std::string>& respHeaders,
                           UTILS::CURL::HTTPResponse& resp);

  static std::string testFile;
  static std::string effectiveUrl;
  static std::vector<std::string> downloadList;
};

class CTestRepresentationChooserDefault : public CHOOSER::CRepresentationChooserDefault
{
public:
  CTestRepresentationChooserDefault() : CHOOSER::CRepresentationChooserDefault() {}
  ~CTestRepresentationChooserDefault() override {}

  void Initialize(const ADP::KODI_PROPS::ChooserProps& props) override
  {
  }
};

class TestAdaptiveStream : public adaptive::AdaptiveStream
{
public:
  TestAdaptiveStream(adaptive::AdaptiveTree* tree,
                     PLAYLIST::CAdaptationSet* adp,
                     PLAYLIST::CRepresentation* initialRepr)
    : adaptive::AdaptiveStream(tree, adp, initialRepr)
  {
  }

  std::chrono::system_clock::time_point mock_time_stream = std::chrono::system_clock::now();
  void SetLastUpdated(const std::chrono::system_clock::time_point tm) override
  {
    lastUpdated_ = tm;
  }
  virtual bool DownloadSegment(const DownloadInfo& downloadInfo) override;

protected:
  virtual bool Download(const DownloadInfo& downloadInfo, std::vector<uint8_t>& data) override;
};

class AESDecrypterTest : public IAESDecrypter
{
public:
  AESDecrypterTest(const std::string& licenseKey) : m_licenseKey(licenseKey) {};
  virtual ~AESDecrypterTest() = default;

  void decrypt(const AP4_UI08* aes_key,
               const AP4_UI08* aes_iv,
               const AP4_UI08* src,
               std::vector<uint8_t>& dst,
               size_t dstOffset,
               size_t& dataSize,
               bool lastChunk);
  std::vector<uint8_t> convertIV(const std::string& input);
  void ivFromSequence(uint8_t* buffer, uint64_t sid);
  const std::string& getLicenseKey() const { return m_licenseKey; };
  // bool RenewLicense(const std::string& pluginUrl);

private:
  std::string m_licenseKey;
};

class DASHTestTree : public adaptive::CDashTree
{
public:
  DASHTestTree() : CDashTree() {}
  uint64_t GetTimestamp() override { return m_mockTime; }
  void SetNowTime(uint64_t time) { m_mockTime = time; }
  void SetLastUpdated(const std::chrono::system_clock::time_point tm) { lastUpdated_ = tm; }
  std::chrono::system_clock::time_point GetNowTimeChrono() { return m_mock_time_chrono; };
  /*!
   * \brief UTCTiming on unit tests by default is disabled, because it may require HTTP requests,
   *        then the clock offset will be forced to be always 0.
   *        By calling this method will allow the parser to resolve UTCTiming fields.
   */
  void EnableUTCTiming() { m_enableUTCTimingResolve = true; }

  /*!
   * \brief Run manually a manifest update with the specified file
   * \return The url used to make the manifest request
   */
  std::string RunManifestUpdate(std::string manifestUpdFile);

private:
  bool DownloadManifestUpd(const std::string& url,
                           const std::map<std::string, std::string>& reqHeaders,
                           const std::vector<std::string>& respHeaders,
                           UTILS::CURL::HTTPResponse& resp) override;

  virtual CDashTree* Clone() const override { return new DASHTestTree{*this}; }

  virtual int64_t ResolveUTCTiming(pugi::xml_node node) override;

  uint64_t m_mockTime = 10000000000;
  std::chrono::system_clock::time_point m_mock_time_chrono = std::chrono::system_clock::now();
  bool m_enableUTCTimingResolve{false};

  std::string m_manifestUpdUrl; // Temporarily stores the url where to request the manifest update
};

class HLSTestTree : public adaptive::CHLSTree
{
public:
  HLSTestTree();

  virtual HLSTestTree* Clone() const override { return new HLSTestTree{*this}; }

private:
  bool DownloadKey(const std::string& url,
                   const std::map<std::string, std::string>& reqHeaders,
                   const std::vector<std::string>& respHeaders,
                   UTILS::CURL::HTTPResponse& resp) override;

  bool DownloadManifestChild(const std::string& url,
                             const std::map<std::string, std::string>& reqHeaders,
                             const std::vector<std::string>& respHeaders,
                             UTILS::CURL::HTTPResponse& resp) override;
};

class SmoothTestTree : public adaptive::CSmoothTree
{
public:
  SmoothTestTree() : CSmoothTree() {}
};
