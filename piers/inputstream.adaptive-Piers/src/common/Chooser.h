/*
 *  Copyright (C) 2022 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#pragma once

#ifdef INPUTSTREAM_TEST_BUILD
#include "test/KodiStubs.h"
#else
#include <kodi/AddonBase.h>
#endif

// forwards
namespace PLAYLIST
{
class CPeriod;
class CAdaptationSet;
class CRepresentation;
}

namespace ADP::KODI_PROPS
{
struct ChooserProps;
}

namespace CHOOSER
{
enum class StreamSelection
{
  AUTO,
  MANUAL,
  MANUAL_VIDEO_ONLY
};

/*!
 * \brief Defines the behaviours on which the quality of streams is chosen
 */
class ATTR_DLL_LOCAL IRepresentationChooser
{
public:
  IRepresentationChooser();
  virtual ~IRepresentationChooser() {}

  /*!
   * \brief Initialize the representation chooser.
   *        (Variables like current screen resolution can be read only with PostInit callback)
   * \param m_kodiProps The Kodi properties
   */
  virtual void Initialize(const ADP::KODI_PROPS::ChooserProps& props) {}

  /*!
   * \brief Post initialization, will be called after the manifest has been opened,
   *        but the DRM is not initialized yet, when done it will be called SetSecureSession method.
   */
  virtual void PostInit() {}

  /*!
   * \brief Callback to update screen resolution.
   */
  void OnUpdateScreenRes();

  /*!
   * \brief Set the current download speed.
   *        To be called at each segment download.
   * \param speed The speed in byte/s
   */
  virtual void SetDownloadSpeed(const double speed) {}

  /*!
   * \brief Get the stream selection mode. Determine whether to provide the user
   *        with the ability to choose a/v tracks from Kodi GUI settings while
   *        in playback.
   * \return The stream selection mode
   */
  virtual StreamSelection GetStreamSelectionMode() { return StreamSelection::AUTO; }

  /*!
   * \brief Called at each DRM initialization to set if the secure session is currently being used.
   * \param isSecureSession Set true if a secure session is in use
   */
  virtual void SetSecureSession(const bool isSecureSession) { m_isSecureSession = isSecureSession; }

  /*!
   * \brief Get the representation from an adaptation set
   * \param adp The adaptation set where choose the representation
   * \return The representation
   */
  PLAYLIST::CRepresentation* GetRepresentation(
      PLAYLIST::CAdaptationSet* adp)
  {
    return GetNextRepresentation(adp, nullptr);
  }

  /*!
   * \brief Get the preferred adaptation set from a period
   *        (a representation may be preselected internally the Chooser)
   * \param period The period where choose the adaptation set / representation
   * \param adpSetPreferred The preferred adaptation set
   * \return The adaptation set or nullptr, the behaviour depend on Chooser implementation
   */
  virtual PLAYLIST::CAdaptationSet* GetPreferredVideoAdpSet(
      PLAYLIST::CPeriod* period, PLAYLIST::CAdaptationSet* adpSetPreferred)
  {
    return adpSetPreferred;
  }

  /*!
   * \brief Get the next representation from an adaptation set
   * \param adp The adaptation set where choose the representation
   * \param currentRep The current representation,
   *        or nullptr for first start or changed to new period
   * \return The next representation
   */
  virtual PLAYLIST::CRepresentation* GetNextRepresentation(
      PLAYLIST::CAdaptationSet* adp,
      PLAYLIST::CRepresentation* currentRep) = 0;

  /*!
   * \brief Prints details of the specified representation in the log
   */
  void LogDetails(const PLAYLIST::CRepresentation* rep);

protected:
  /*!
   * \brief Prints details of the selected or changed representation in the log
   */
  void LogDetails(const PLAYLIST::CRepresentation* currentRep,
                  const PLAYLIST::CRepresentation* nextRep);

  bool m_isSecureSession{false};

  // Current screen width resolution (this value is auto-updated by Kodi)
  int m_screenCurrentWidth{0};
  // Current screen height resolution (this value is auto-updated by Kodi)
  int m_screenCurrentHeight{0};
  // Specifies when it is necessary to start playback with a stream having
  // max allowed resolution to let Kodi auto-switching the screen resolution
  // with "Adjust refresh rate" setting
  bool m_isForceStartsMaxRes{false};

private:
  bool m_isAdjustRefreshRate{false};
};

IRepresentationChooser* CreateRepresentationChooser();

} // namespace CHOOSER
