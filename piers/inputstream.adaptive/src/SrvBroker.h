/*
 *  Copyright (C) 2023 Team Kodi
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

#include <map>
#include <memory>
#include <string>

// forward
namespace ADP::RESOURCES
{
class CCompResources;
}
namespace ADP::SETTINGS
{
class CCompSettings;
}
namespace ADP::KODI_PROPS
{
class CCompKodiProps;
}
namespace adaptive
{
class AdaptiveTree;
}

/*
 * \brief Service broker is a singleton that give an easy access to the resources from anywhere in the code.
 */
class ATTR_DLL_LOCAL CSrvBroker
{
public:
  CSrvBroker(CSrvBroker& other) = delete; // Not clonable
  void operator=(const CSrvBroker&) = delete; // Not assignable

  /*
   * \brief Initialize service broker components, when the add-on is created.
   */
  void Initialize();

  /*
   * \brief Initialize service broker components, on addon initialization.
   */
  void InitStage1(const std::map<std::string, std::string>& kodiProps);

  /*
   * \brief Initialize service broker components, on session initialization.
   * \param tree The adaptive tree
   */
  void InitStage2(adaptive::AdaptiveTree* tree);

  static CSrvBroker* GetInstance()
  {
    static CSrvBroker instance;
    return &instance;
  }

  /*
   * \brief Deinitialize service broker components, when the add-on is terminated.
   */
  void Deinitialize();

  /*
   * \brief Get Kodi properties component, to read Kodi (Listitem / playlist files "STRM") properties.
   */
  static ADP::KODI_PROPS::CCompKodiProps& GetKodiProps()
  {
    return *GetInstance()->m_compKodiProps;
  }

  /*
   * \brief Get resources component, for shared resources.
   */
  static ADP::RESOURCES::CCompResources& GetResources()
  {
    return *GetInstance()->m_compResources;
  }

  /*
   * \brief Get settings component, to manage add-on XML settings.
   */
  static ADP::SETTINGS::CCompSettings& GetSettings()
  {
    return *GetInstance()->m_compSettings;
  }

private:
  CSrvBroker();
  ~CSrvBroker();

  std::unique_ptr<ADP::KODI_PROPS::CCompKodiProps> m_compKodiProps;
  std::unique_ptr<ADP::RESOURCES::CCompResources> m_compResources;
  std::unique_ptr<ADP::SETTINGS::CCompSettings> m_compSettings;
};
