/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace UTILS
{
namespace URL
{
/*! \brief Check if it is a valid URL
 *  \return True if it is a valid URL, false otherwise
 */
bool IsValidUrl(const std::string& url);

/*! \brief Check if it is an absolute URL
 *  \return True if it is an absolute URL, false otherwise
 */
bool IsUrlAbsolute(std::string_view url);

/*! \brief Check if it is a relative URL e.g. "/something/"
 *  \param url An URL
 *  \return True if it is a relative URL, false otherwise
 */
bool IsUrlRelative(std::string_view url);

/*! \brief Check if it is a relative URL to a level e.g. "../something/"
 *  \param url An URL
 *  \return True if it is a relative URL to a level, false otherwise
 */
bool IsUrlRelativeLevel(std::string_view url);

/*! \brief Get URL parameters e.g. "?q=something"
 *  \param url An URL
 *  \return The URL parameters
 */
std::string GetParameters(std::string& url);

/*!
 * \brief Remove URL parameters e.g. "?q=something"
 * \param url An URL
 * \return The URL without parameters
 */
std::string RemoveParameters(std::string url);

/*!
 * \brief Get the path part of an url,
 *        e.g. https://sample.com/part1/part2?test become /part1/
 * \param url An URL
 * \param includeFilePart If true, keep the file name of the path
 * \return The path
 */
std::string GetPath(std::string url, bool includeFilePart);

/*!
 * \brief Get the url path, by removing file part and parameters
 *        e.g. https://sample.com/part1/part2?test become https://sample.com/part1/
 * \param url An URL
 * \return The URL path
 */
std::string GetUrlPath(std::string url);

/*! \brief Append a string of parameters to an URL without overwriting existing params values
 *  \param url URL where append the parameters
 *  \param params Params to be appended
 */
void AppendParameters(std::string& url, std::string_view params);

/*! \brief Get the base domain of an URL
 *  \param url An URL
 *  \return The base domain URL if found, otherwise empty string
 */
std::string GetBaseDomain(std::string url);

/*! 
 * \brief Combine two URLs as per RFC 3986 specification.
 * \param baseUrl The base URL, absolute or relative.
 * \param relativeUrl The other relative URL to be combined.
 * \return The final URL.
 */
std::string Join(std::string baseUrl, std::string relativeUrl);

/*!
 * \brief Ensure that the URL address ends with backslash "/".
 * \param url[IN][OUT] An URL.
 */
void EnsureEndingBackslash(std::string& url);

/*!
 * \brief Remove the part of the URL that starts with the pipe char "|".
 * \param url[IN][OUT] An URL.
 */
void RemovePipePart(std::string& url);

/*!
 * \brief Check if a string contains a valid URI scheme.
 * \param uri An URI.
 * \param scheme[OPT] A scheme, by default "data".
 */
bool IsValidUri(const std::string& uri, std::string_view scheme = "data");

/*!
 * \brief Get the byte data from an URI.
 * \param uri[IN] An URL.
 * \param data[OUT] The byte read.
 * \return Always returns true if it is a URI data format (starts with "data:"),
 *         even if it contains malformed data. Any other string that is not in URI data format returns false.
 */
bool GetUriByteData(std::string_view uri, std::vector<uint8_t>& data);

} // namespace URL
} // namespace UTILS
