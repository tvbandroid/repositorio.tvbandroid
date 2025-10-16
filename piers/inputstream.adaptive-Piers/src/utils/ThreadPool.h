/*
 *  Copyright (C) 2025 Team Kodi
 *  This file is part of Kodi - https://kodi.tv
 *
 *  SPDX-License-Identifier: GPL-2.0-or-later
 *  See LICENSES/README.md for more information.
 */

#include <condition_variable>
#include <exception>
#include <functional>
#include <future>
#include <mutex>
#include <optional>
#include <queue>
#include <thread>
#include <vector>

#pragma once

namespace UTILS::THREAD
{

/*!
 * \brief A simple thread pool
 *
 * The thread pool automatically grows if there are more concurrent tasks then
 * threads. Automatic shrinking is not implemented but this could easily be
 * added if desired.
 */
class ThreadPool
{
public:
  ThreadPool() = default;
  ~ThreadPool() = default;

  ThreadPool(ThreadPool& other) = delete; // Not clonable
  void operator=(const ThreadPool&) = delete; // Not assignable

  /*!
   * \brief Execute a callable on a thread pool thread
   *
   * \attention If the `std::future` obtained from this function is not moved
   * from or bound to a reference, the destructor of the `std::future` will
   * block at the end of the full expression until the asynchronous operation
   * completes, essentially making the call synchronous.
   */
  template<class F, class... Args>
  [[nodiscard]] auto Execute(F&& f, Args&&... args) -> auto
  {
    using return_type = decltype(std::invoke(f, args...));

    std::future<return_type> future;

    {
      std::lock_guard lock(m_mutex);

      if (m_isStopped)
      {
        std::promise<return_type> p;
        p.set_exception(
            std::make_exception_ptr(std::runtime_error("ThreadPool has already been stopped")));
        return p.get_future();
      }

      auto task = std::make_shared<std::packaged_task<return_type()>>(
          std::bind(std::forward<F>(f), std::forward<Args>(args)...));
      future = task->get_future();

      m_taskQueue.emplace([task = std::move(task)]() { (*task)(); });

      // Check if there are enough executors for the number of task, if not create more
      if (m_executors.size() - m_activeExecutors < m_taskQueue.size())
        m_executors.emplace_back(std::make_unique<Executor>(*this));
    }

    m_condVar.notify_one();

    return future;
  }

  /*!
   * \brief Don't allow execution of new tasks and block until all running tasks completed
   */
  void Stop();

  /*!
   * \brief Don't allow execution of new tasks and block until all running tasks completed, then reset the thread pool
   */
  void Reset();

private:
  class Executor
  {
  public:
    Executor(ThreadPool& threadPool);
    void Join();

  private:
    ThreadPool* m_threadPool;
    std::thread m_thread;
    void Run();
  };

  /*!
   * \brief Returns a task or nothing, if nothing is returned the Executor should exit
   */
  std::optional<std::function<void()>> TakeTask();
  /*!
   * \brief Informs the thread pool that a task is done and the Executor is available again
   */
  void TaskFinished();

  // Executors need to be on the heap for a stable `this` pointer
  std::vector<std::unique_ptr<Executor>> m_executors;
  std::queue<std::function<void()>> m_taskQueue;
  std::mutex m_mutex;
  std::condition_variable m_condVar;
  size_t m_activeExecutors{0};
  bool m_isStopped{false};
};

extern ThreadPool GlobalThreadPool;

} // namespace UTILS::THREAD
