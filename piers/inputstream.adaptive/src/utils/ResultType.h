/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include <string>

// SResult status codes
enum class SResultCode
{
  OK,
  ERROR, // Generic error
};

/*!
 * \brief Handles return status of operations. It can be tested also as a bool type.
 */
struct SResult
{
  SResult(SResultCode setCode, const std::string& setMessage = "")
    : code(setCode), message(setMessage)
  {
  }

  operator bool() const { return code == SResultCode::OK; }

  // \brief Get the result code
  SResultCode Code() const { return code; }
  // \brief Get the (optional) message
  const std::string& Message() const { return message; }

  // \brief Return true when the operation is failed
  bool IsFailed() const { return code != SResultCode::OK; }

  static SResult Ok(const std::string& setMessage = "") { return {SResultCode::OK, setMessage}; }
  static SResult Error(const std::string& setMessage = "")
  {
    return {SResultCode::ERROR, setMessage};
  }
  static SResult Fail(SResultCode setCode, const std::string& setMessage = "")
  {
    return {setCode, setMessage};
  }

protected:
  SResultCode code;
  std::string message;
};
