/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "WVCdmAdapter.h"

#include "CdmFixedBuffer.h"
#include "WVCencSingleSampleDecrypter.h"
#include "WVDecrypter.h"
#include "cdm/debug.h"
#include "decrypters/Helpers.h"
#include "utils/FileUtils.h"
#include "utils/GUIUtils.h"
#include "utils/log.h"

#include <array>
#include <filesystem>
#include <ranges>
#include <string_view>

using namespace UTILS;

namespace
{
#if WIN32
constexpr const char* LIBRARY_FILENAME = "widevinecdm.dll";
#elif TARGET_DARWIN
constexpr const char* LIBRARY_FILENAME = "libwidevinecdm.dylib";
#elif TARGET_WEBOS
constexpr std::array<std::string_view, 2> candidatePaths = {"/usr/lib/libwidevine-wrapper.so",
                                                            "/usr/lib/libwvcdm_shared.so"};
#else
constexpr const char* LIBRARY_FILENAME = "libwidevinecdm.so";
#endif

void DebugLog(const CDM_DBG::LogLevel level, const char* msg)
{
  switch (level)
  {
    case CDM_DBG::LogLevel::ERROR:
      LOG::Log(LOGERROR, msg);
      break;
    case CDM_DBG::LogLevel::WARNING:
      LOG::Log(LOGWARNING, msg);
      break;
    case CDM_DBG::LogLevel::INFO:
      LOG::Log(LOGINFO, msg);
      break;
    case CDM_DBG::LogLevel::DEBUG:
      LOG::Log(LOGDEBUG, msg);
      break;
    case CDM_DBG::LogLevel::FATAL:
      LOG::Log(LOGFATAL, msg);
      break;
    default:
      break;
  }
}
} // unnamed namespace

CWVCdmAdapter::CWVCdmAdapter()
{
  CDM_DBG::SetDBGMsgCallback(DebugLog);
}

CWVCdmAdapter::~CWVCdmAdapter()
{
  if (m_cdmAdapter)
  {
    m_cdmAdapter->RemoveClient();
    // LOG::LogF(LOGDEBUG, "CDM Adapter instances: %u", m_cdmAdapter.use_count());
    m_cdmAdapter = nullptr;
  }
}

SResult CWVCdmAdapter::Initialize(const DRM::Config& config, CWVDecrypter* host)
{
  m_config = config;
  m_host = host;

  if (m_host->GetLibraryPath().empty())
  {
    LOG::LogF(LOGERROR, "Widevine CDM library path not specified");
    return SResultCode::ERROR;
  }
  std::string cdmPath;
  bool useHwSecureCodecs = false;
#ifdef TARGET_WEBOS
  useHwSecureCodecs = true;
  auto it = std::ranges::find_if(candidatePaths, [](std::string_view sv)
                                 { return std::filesystem::exists(std::filesystem::path{sv}); });

  if (it != candidatePaths.end())
  {
    cdmPath = std::string(*it);
  }
  else
  {
    LOG::LogF(LOGERROR, "Widevine CDM library not found");
    return SResultCode::ERROR;
  }
#else
  cdmPath = FILESYS::PathCombine(m_host->GetLibraryPath(), LIBRARY_FILENAME);
#endif

  // The license url come from license_key kodi property
  // we have to kept only the url without the parameters specified after pipe "|" char
  std::string licUrl = m_config.license.serverUri;
  const size_t urlPipePos = licUrl.find('|');
  if (urlPipePos != std::string::npos)
    licUrl.erase(urlPipePos);

  // Build up a CDM path to store decrypter specific stuff, each domain gets it own path
  // the domain name is hashed to generate a short folder name
  std::string basePath = FILESYS::PathCombine(FILESYS::GetAddonUserPath(), "widevine");
  basePath = FILESYS::PathCombine(basePath, DRM::GenerateUrlDomainHash(licUrl));
  basePath += FILESYS::SEPARATOR;

  auto cdmAdapter = std::make_shared<media::CdmAdapter>(
      "com.widevine.alpha", cdmPath, basePath,
      media::CdmConfig(false, m_config.isPersistentStorage, useHwSecureCodecs),
      dynamic_cast<media::CdmAdapterClient*>(this));

  if (!cdmAdapter->LoadCDM())
  {
    LOG::Log(LOGERROR, "Unable to load widevine shared library (%s)", cdmPath.c_str());
    return SResult::Error(GUI::GetLocalizedString(30304));
  }

  if (!cdmAdapter->Initialize())
    return SResult::Error(GUI::GetLocalizedString(30305));

  const std::vector<uint8_t>& cert = m_config.license.serverCert;
  if (!cert.empty())
  {
    cdmAdapter->SetServerCertificate(0, cert.data(), static_cast<uint32_t>(cert.size()));
  }

  // cdmAdapter->GetStatusForPolicy();
  // cdmAdapter->QueryOutputProtectionStatus();

  m_cdmAdapter = cdmAdapter;
  return SResultCode::OK;
}

void CWVCdmAdapter::OnCDMMessage(const char* session,
                          uint32_t session_size,
                          CDMADPMSG msg,
                          const uint8_t* data,
                          size_t data_size,
                          uint32_t status)
{
  LOG::Log(LOGDEBUG, "CDM message: type %i arrived", msg);

  CdmMessageType type;
  if (msg == CDMADPMSG::kSessionMessage)
    type = CdmMessageType::SESSION_MESSAGE;
  else if (msg == CDMADPMSG::kSessionKeysChange)
    type = CdmMessageType::SESSION_KEY_CHANGE;
  else
    return;

  CdmMessage cdmMsg;
  cdmMsg.sessionId.assign(session, session + session_size);
  cdmMsg.type = type;
  cdmMsg.data.assign(data, data + data_size);
  cdmMsg.status = status;

  // Send the message to attached CWVCencSingleSampleDecrypter instances
  NotifyObservers(cdmMsg);
}

cdm::Buffer* CWVCdmAdapter::AllocateBuffer(size_t sz)
{
  VIDEOCODEC_PICTURE pic;
  pic.decodedDataSize = sz;
  if (m_host->GetBuffer(m_codecInstance, pic))
  {
    CdmFixedBuffer* buf = new CdmFixedBuffer;
    buf->initialize(m_codecInstance, pic.decodedData, pic.decodedDataSize, pic.videoBufferHandle, m_host);
    return buf;
  }
  return nullptr;
}

const DRM::Config& CWVCdmAdapter::GetConfig()
{
  return m_config;
}

void CWVCdmAdapter::SetCodecInstance(void* instance)
{
  m_codecInstance = reinterpret_cast<kodi::addon::CInstanceVideoCodec*>(instance);
}

void CWVCdmAdapter::ResetCodecInstance()
{
  m_codecInstance = nullptr;
}

std::string_view CWVCdmAdapter::GetKeySystem()
{
  return KS_WIDEVINE;
}

std::string_view CWVCdmAdapter::GetLibraryPath() const
{
  return m_host->GetLibraryPath();
}

void CWVCdmAdapter::AttachObserver(IWVObserver* observer)
{
  std::lock_guard<std::mutex> lock(m_observer_mutex);
  m_observers.emplace_back(observer);
}

void CWVCdmAdapter::DetachObserver(IWVObserver* observer)
{
  std::lock_guard<std::mutex> lock(m_observer_mutex);
  m_observers.remove(observer);
}

void CWVCdmAdapter::NotifyObservers(const CdmMessage& message)
{
  std::lock_guard<std::mutex> lock(m_observer_mutex);
  for (IWVObserver* observer : m_observers)
  {
    if (observer)
      observer->OnNotify(message);
  }
}
