// SPDX-License-Identifier: MPL-2.0

#[cfg(all(feature = "cosmic-winit", feature = "cosmic-wayland"))]
compile_error!("enable exactly one of cosmic-winit or cosmic-wayland");

#[cfg(not(any(feature = "cosmic-winit", feature = "cosmic-wayland")))]
fn main() -> anyhow::Result<()> {
    let backend = neodash_platform::detect_backend_from_env();

    println!("NeoDash native COSMIC host scaffold");
    println!(
        "detected: {:?} / {:?} / {:?}",
        backend.desktop_family, backend.display_protocol, backend.kind
    );
    println!("reason: {}", backend.reason);
    println!();
    println!("This binary was built without libcosmic support.");
    println!();
    println!("Run the frontend on the current X11/non-COSMIC desktop:");
    println!("  cargo run -p neodash-cosmic --features cosmic-winit");
    println!();
    println!("Compile the native COSMIC Wayland target:");
    println!("  cargo check -p neodash-cosmic --features cosmic-wayland");

    Ok(())
}

#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]
fn main() -> cosmic::iced::Result {
    cosmic_host::run()
}

#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]
mod cosmic_host {
    use cosmic::iced::Length;
    use cosmic::prelude::*;
    use cosmic::widget;
    use neodash_platform::{BackendInfo, detect_backend_from_env};

    pub fn run() -> cosmic::iced::Result {
        cosmic::app::run::<NeoDashCosmicApp>(cosmic::app::Settings::default(), ())
    }

    pub struct NeoDashCosmicApp {
        core: cosmic::Core,
        platform: BackendInfo,
    }

    impl cosmic::Application for NeoDashCosmicApp {
        type Executor = cosmic::executor::Default;
        type Flags = ();
        type Message = ();

        const APP_ID: &'static str = "io.github.adamjvr.NeoDash.Cosmic";

        fn core(&self) -> &cosmic::Core {
            &self.core
        }

        fn core_mut(&mut self) -> &mut cosmic::Core {
            &mut self.core
        }

        fn init(
            core: cosmic::Core,
            _flags: Self::Flags,
        ) -> (Self, Task<cosmic::Action<Self::Message>>) {
            (
                Self {
                    core,
                    platform: detect_backend_from_env(),
                },
                Task::none(),
            )
        }

        fn view(&self) -> Element<'_, Self::Message> {
            let spacing = cosmic::theme::spacing().space_m;
            let content = widget::column::with_capacity(5)
                .push(widget::text::title1("NeoDash"))
                .push(widget::text::title3("Native COSMIC frontend scaffold"))
                .push(widget::text::body(format!(
                    "Desktop: {:?}",
                    self.platform.desktop_family
                )))
                .push(widget::text::body(format!(
                    "Display: {:?}",
                    self.platform.display_protocol
                )))
                .push(widget::text::body(format!(
                    "Integration backend: {:?}",
                    self.platform.kind
                )))
                .spacing(spacing);

            widget::container(content)
                .padding(spacing)
                .width(Length::Fill)
                .height(Length::Fill)
                .into()
        }

        fn update(&mut self, _message: Self::Message) -> Task<cosmic::Action<Self::Message>> {
            Task::none()
        }
    }
}
