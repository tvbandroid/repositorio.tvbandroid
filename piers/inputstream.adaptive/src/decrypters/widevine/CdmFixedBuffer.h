/*
 *  Copyright (C) 2023 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include "CdmBuffer.h"

class CWVDecrypter;

class ATTR_DLL_LOCAL CdmFixedBuffer : public cdm::Buffer
{
public:
  CdmFixedBuffer() {}
  virtual ~CdmFixedBuffer() {}

  virtual void Destroy() override;

  virtual uint32_t Capacity() const override { return m_capacity; };

  virtual uint8_t* Data() override { return m_data; };

  virtual void SetSize(uint32_t size) override { m_dataSize = size; };

  virtual uint32_t Size() const override { return m_dataSize; };

  void initialize(void* instance, uint8_t* data, size_t dataSize, void* buffer, CWVDecrypter* host);

  void* Buffer() const { return m_buffer; };

private:
  uint8_t* m_data{nullptr};
  uint32_t m_dataSize{0};
  uint32_t m_capacity{0};
  void* m_buffer{nullptr};
  void* m_instance{nullptr};
  CWVDecrypter* m_host{nullptr};
};
