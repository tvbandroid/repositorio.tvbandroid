/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include "Stream.h"

using namespace SESSION;

void CStream::Disable()
{
  if (m_isEnabled)
  {
    m_adStream.Disable();
    // Stop method stop the downloads, but not the reader.
    m_adStream.Stop();
    // The reader is an async thread and may still working to read buffer data,
    // so wait for it to exit before the AdaptiveStream::Dispose call,
    // otherwise it will cause data access violation on buffers because still in use
    if (m_streamReader)
      m_streamReader->WaitReadSampleAsyncComplete();

    m_adStream.Dispose();

    Reset();

    m_isEnabled = false;
  }
}

void CStream::Reset()
{
  if (m_isEnabled)
  {
    if (m_streamReader)
      m_streamReader->WaitReadSampleAsyncComplete();
    m_streamReader.reset();
    m_streamFile.reset();
    m_adByteStream.reset();
    m_mainStreamIndex.reset();
  }
}

void SESSION::CStream::SetReader(std::unique_ptr<ISampleReader> reader)
{
  m_streamReader = std::move(reader);
  m_streamReader->SetObserver(&m_adStream);
}
